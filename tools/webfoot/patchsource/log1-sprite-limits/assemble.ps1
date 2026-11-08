param(
    [string] $Out = ''
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$as = 'C:\devkitPro\devkitARM\bin\arm-none-eabi-as.exe'
$objcopy = 'C:\devkitPro\devkitARM\bin\arm-none-eabi-objcopy.exe'
$objdump = 'C:\devkitPro\devkitARM\bin\arm-none-eabi-objdump.exe'
foreach ($tool in @($as, $objcopy)) {
    if (-not (Test-Path $tool)) { throw "missing tool: $tool" }
}
$outDir = if ($Out) { $Out } else { $here }

foreach ($name in 'budget', 'bank') {
    $obj = Join-Path $outDir "$name.o"
    $bin = Join-Path $outDir "$name.bin"
    & $as -mcpu=arm7tdmi -mthumb -o $obj (Join-Path $here "$name.s")
    if ($LASTEXITCODE -ne 0) { throw "assembler failed for ${name}: $LASTEXITCODE" }
    & $objcopy -O binary --only-section=.text $obj $bin
    if ($LASTEXITCODE -ne 0) { throw "objcopy failed for ${name}: $LASTEXITCODE" }
    $bytes = [System.IO.File]::ReadAllBytes($bin)
    "{0}.bin {1} B sha256 {2}" -f $name, $bytes.Length, (Get-FileHash $bin -Algorithm SHA256).Hash.ToLowerInvariant()
}
"disassembly (budget.bin):"
& $objdump -D -b binary -m arm -M force-thumb (Join-Path $outDir 'budget.bin') |
    Select-String -Pattern '^\s+[0-9a-f]+:' | ForEach-Object { $_.Line }
"disassembly (bank.bin):"
& $objdump -D -b binary -m arm -M force-thumb (Join-Path $outDir 'bank.bin') |
    Select-String -Pattern '^\s+[0-9a-f]+:' | ForEach-Object { $_.Line }
