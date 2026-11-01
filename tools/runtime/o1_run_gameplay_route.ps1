param(
    [string]$RomPath = 'build\o1-log2-16mib.gba',
    [string]$LuaPath = 'tools\runtime\o1_clean_gameplay_route.lua',
    [string]$MgbaPath = 'build\mgba-lua\mGBA.exe',
    [string]$MGBSha256 = '5A3C98C2984DD04BD0D7C9378CDFAE937AE0D73A196C880BB2EECF3B254AF247',
    [string]$RequiredMGBVersion = '0.10.5',
    [int]$ExpectedRomSize = 16777216,
    [int]$TimeoutSeconds = 240
)

$ErrorActionPreference = 'Stop'
$workspaceRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))

function Resolve-Under([string]$p) {
    if ([System.IO.Path]::IsPathRooted($p)) { return [System.IO.Path]::GetFullPath($p) }
    return [System.IO.Path]::GetFullPath((Join-Path $workspaceRoot $p))
}

$rom = Resolve-Under $RomPath
$lua = Resolve-Under $LuaPath
$mgb = Resolve-Under $MgbaPath

foreach ($f in @($rom, $lua, $mgb)) {
    if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { throw "missing: $f" }
}

$mgbVersion = (Get-Item -LiteralPath $mgb).VersionInfo.FileVersion
if (-not $mgbVersion -or -not $mgbVersion.StartsWith($RequiredMGBVersion)) {
    throw "mGBA version mismatch: required $RequiredMGBVersion, found $mgbVersion"
}
$mgbHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $mgb).Hash
if ($mgbHash -ne $MGBSha256.Trim().ToUpperInvariant()) {
    throw "mGBA identity mismatch: required $MGBSha256, found $mgbHash"
}

$romItem = Get-Item -LiteralPath $rom
$beforeHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $rom).Hash
$beforeMtime = $romItem.LastWriteTimeUtc.Ticks
if ($romItem.Length -ne $ExpectedRomSize) {
    throw "ROM is $($romItem.Length) bytes, expected $ExpectedRomSize"
}

$runRoot = Join-Path $workspaceRoot ('build\o1-evidence\route-' + [Guid]::NewGuid().ToString('N'))
foreach ($d in @('save', 'states', 'screenshots')) {
    $null = New-Item -ItemType Directory -Force -Path (Join-Path $runRoot $d)
}
$routeOut = Join-Path $runRoot 'route.csv'
$readyPath = Join-Path $runRoot 'route-ready.txt'

$env:O1_ROUTE_OUT = $routeOut
$env:O1_SHOT_PREFIX = (Join-Path $runRoot 'shot')

$arguments = @(
    '-C', ('savegamePath=' + (Join-Path $runRoot 'save')),
    '-C', ('savestatePath=' + (Join-Path $runRoot 'states')),
    '-C', ('screenshotPath=' + (Join-Path $runRoot 'screenshots')),
    '-C', 'mute=1',
    '-C', 'audioSync=0',
    '-C', 'videoSync=0',
    ('"' + $rom + '"')
)

"emulator sha256 : $mgbHash"
"emulator version: $mgbVersion"
"rom             : $rom"
"rom size        : $($romItem.Length)"
"rom sha256      : $beforeHash"
"run root        : $runRoot"

$process = Start-Process -FilePath $mgb -ArgumentList $arguments -PassThru
try {
    & (Join-Path $PSScriptRoot 'inject_mgba_lua.ps1') `
        -TargetProcessId $process.Id `
        -LuaPath $lua `
        -ReadyPath $readyPath `
        -WindowTitlePattern 'DBZLGCYGOKU2|Legacy of Goku'

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $done = $false
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $routeOut) {
            $tail = Get-Content -LiteralPath $routeOut -Tail 1 -ErrorAction SilentlyContinue
            if ($tail -match 'route-complete') { $done = $true; break }
        }
        if ($process.HasExited) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $done) {
        "WARNING: route did not report route-complete within $TimeoutSeconds s"
    }
}
finally {
    if (-not $process.HasExited) {
        $process.CloseMainWindow() | Out-Null
        Start-Sleep -Milliseconds 500
        if (-not $process.HasExited) { $process.Kill() }
    }
    Remove-Item Env:\O1_ROUTE_OUT -ErrorAction SilentlyContinue
    Remove-Item Env:\O1_SHOT_PREFIX -ErrorAction SilentlyContinue
}

$afterItem = Get-Item -LiteralPath $rom
$afterHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $rom).Hash
if ($afterHash -ne $beforeHash -or $afterItem.Length -ne $romItem.Length -or $afterItem.LastWriteTimeUtc.Ticks -ne $beforeMtime) {
    throw 'ROM changed during the route run'
}

"rom unchanged   : True"
"route csv       : $routeOut"
if (Test-Path -LiteralPath $routeOut) {
    $rows = Get-Content -LiteralPath $routeOut
    "route rows      : $($rows.Count)"
    "--- first 5 ---"
    $rows | Select-Object -First 5
    "--- last 5 ---"
    $rows | Select-Object -Last 5
}
