param(
    [string] $Out = ''
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$as      = 'C:\devkitPro\devkitARM\bin\arm-none-eabi-as.exe'
$objcopy = 'C:\devkitPro\devkitARM\bin\arm-none-eabi-objcopy.exe'
$nm      = 'C:\devkitPro\devkitARM\bin\arm-none-eabi-nm.exe'
$readelf = 'C:\devkitPro\devkitARM\bin\arm-none-eabi-readelf.exe'
foreach ($tool in @($as, $objcopy, $nm, $readelf)) {
    if (-not (Test-Path $tool)) { throw "missing tool: $tool" }
}
$outDir = if ($Out) { $Out } else { $here }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

function Get-SymbolOffsets([string] $obj, [string] $pattern) {
    $table = @{}
    & $nm -n $obj | ForEach-Object {
        $parts = $_ -split '\s+'
        if ($parts.Count -ge 3 -and $parts[2] -match $pattern) {
            $table[$parts[2]] = [Convert]::ToInt32($parts[0], 16)
        }
    }
    return $table
}

function Assert-NoRelocations([string] $obj) {
    $text = (& $readelf -r $obj) -join "`n"
    if ($text -match 'contains\s+[1-9]') { throw "unresolved ELF relocations in $obj" }
}

function Split-Payload([string] $source, [string[]] $symbols, [string[]] $labels,
                       [string] $fixupSymbol, [string] $fixupLabel) {
    $obj = Join-Path $outDir ([System.IO.Path]::GetFileNameWithoutExtension($source) + '.o')
    $bin = Join-Path $outDir ([System.IO.Path]::GetFileNameWithoutExtension($source) + '.bin')
    & $as -mcpu=arm7tdmi -mthumb -o $obj (Join-Path $here $source)
    if ($LASTEXITCODE -ne 0) { throw "assembler failed: $source exit $LASTEXITCODE" }
    Assert-NoRelocations $obj
    & $objcopy -O binary --only-section=.text $obj $bin
    if ($LASTEXITCODE -ne 0) { throw "objcopy failed: $bin" }
    $sizes = Get-SymbolOffsets $obj '^(bf_box_|bf_text_|resource_words|text_fixups|oam_table|affine_ramp)'
    foreach ($name in $symbols + $fixupSymbol) {
        if (-not $sizes.ContainsKey($name)) { throw "symbol $name missing from $obj" }
    }
    foreach ($name in $symbols + $fixupSymbol) {
        if ($sizes[$name] % 4) {
            throw "$name starts at 0x$('{0:x}' -f $sizes[$name]) in $source; a split entry and every fixup word must be 4-byte aligned"
        }
    }
    $raw = [System.IO.File]::ReadAllBytes($bin)
    for ($i = 0; $i -lt $symbols.Count; $i++) {
        $start = $sizes[$symbols[$i]]
        $end = if ($i + 1 -lt $symbols.Count) { $sizes[$symbols[$i + 1]] } else { $raw.Length }
        $slice = New-Object byte[] ($end - $start)
        [Array]::Copy($raw, $start, $slice, 0, $end - $start)
        [System.IO.File]::WriteAllBytes((Join-Path $outDir ($labels[$i] + '.bin')), $slice)
    }
    $fw = $sizes[$fixupSymbol] - $sizes[$symbols[[array]::IndexOf($labels, $fixupLabel)]]
    $payload = Join-Path $outDir ($fixupLabel + '.bin')
    $bytes = [System.IO.File]::ReadAllBytes($payload)
    if ($fw % 4) { throw "fixup word at 0x$('{0:x}' -f $fw) of $payload is not 4-byte aligned" }
    if ($fw + 12 -gt $bytes.Length) { throw "fixup words fall outside $payload" }
    for ($k = 0; $k -lt 12; $k++) {
        if ($bytes[$fw + $k] -ne 0) { throw "fixup word byte $k is not zero in $payload" }
    }
    return @{ length = $raw.Length; bin = $bin; fixup = $fw; fixupPayload = $fixupLabel }
}

$box = Split-Payload 'box.s' `
    @('bf_box_geometry', 'bf_box_strips', 'bf_box_window') `
    @('bf-box-geometry', 'bf-box-strips', 'bf-box-window') 'resource_words' 'bf-box-strips'
$text = Split-Payload 'text.s' @('bf_text_update') @('text') 'text_fixups' 'text'

"box.bin {0} B sha256 {1}" -f $box.length, (Get-FileHash $box.bin -Algorithm SHA256).Hash.ToLowerInvariant()
foreach ($name in 'bf-box-geometry', 'bf-box-strips', 'bf-box-window') {
    $path = Join-Path $outDir ($name + '.bin')
    "{0}.bin {1} B sha256 {2}" -f $name, (Get-Item $path).Length,
        (Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant()
}
"box fixups: box_raster at 0x{0:x} (10240 B), portrait_payload at 0x{1:x}, lifecycle_table at 0x{2:x}, palette_low128 at 0x{3:x} in {4}" -f
    $box.fixup, ($box.fixup + 4), ($box.fixup + 8), ($box.fixup + 12), $box.fixupPayload
"text.bin {0} B sha256 {1}" -f $text.length, (Get-FileHash $text.bin -Algorithm SHA256).Hash.ToLowerInvariant()
"text fixups: box_raster at 0x{0:x} (10240 B), font_blob at 0x{1:x} (3598 B), lifecycle_table at 0x{2:x} in text.bin" -f
    $text.fixup, ($text.fixup + 4), ($text.fixup + 8)
