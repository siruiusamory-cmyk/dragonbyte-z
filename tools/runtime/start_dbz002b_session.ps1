[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RomPath,
    [Parameter(Mandatory = $true)]
    [string]$RomSha256,
    [Parameter(Mandatory = $true)]
    [string]$Label,
    [string]$StatePath,
    [string]$LuaPath = 'tools\runtime\dbz002b_entry_watch.lua',
    [string]$DriverPath = 'tools\runtime\dbz002b_route_driver.lua',
    [string]$MGBPath = 'C:\Program Files\mGBA\mGBA.exe',
    [string]$RequiredMGBVersion = '0.11',
    [int]$MaxFrames = 4600,
    [int]$DriveFrames = 1400,
    [string]$Route = 'clone',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path

function Resolve-Required([string]$Path, [string]$What) {
    $candidate = if ([System.IO.Path]::IsPathRooted($Path)) { $Path } else { Join-Path $root $Path }
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw "$What is missing: $candidate"
    }
    return (Resolve-Path -LiteralPath $candidate).Path
}

$resolvedRom = Resolve-Required $RomPath 'ROM'
$resolvedLua = Resolve-Required $LuaPath 'Lua observer'
$resolvedDriver = Resolve-Required $DriverPath 'Lua driver'
$resolvedMGB = Resolve-Required $MGBPath 'mGBA'
$resolvedState = $null
if ($StatePath) { $resolvedState = Resolve-Required $StatePath 'Savestate' }

$mgbVersion = (Get-Item -LiteralPath $resolvedMGB).VersionInfo.FileVersion
if (-not $mgbVersion.StartsWith($RequiredMGBVersion)) {
    throw "mGBA version mismatch: required $RequiredMGBVersion, found $mgbVersion"
}

$expected = $RomSha256.Trim().ToUpperInvariant()
if ($expected -notmatch '^[0-9A-F]{64}$') {
    throw 'RomSha256 must be a full 64-character SHA-256 hex digest'
}
$romInfo = Get-Item -LiteralPath $resolvedRom
$romHashBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedRom).Hash
if ($romHashBefore -ne $expected) {
    throw "ROM identity mismatch; run refused. Expected $expected, found $romHashBefore"
}

if (Get-Process mGBA -ErrorAction SilentlyContinue) {
    throw 'An mGBA process is already running; close it first (a failed run can leave one holding the GDB port).'
}

$stateHash = ''
if ($resolvedState) { $stateHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedState).Hash }

$runDir = Join-Path $root ("build\dbz002b\" + $Label)
if (Test-Path -LiteralPath $runDir) {
    throw "Run directory already exists: $runDir - pass a different -Label."
}

if ($DryRun) {
    Write-Output 'DRY RUN - nothing launched, nothing written'
    Write-Output "  label     : $Label"
    Write-Output "  rom       : $resolvedRom"
    Write-Output "  rom sha   : $romHashBefore ($($romInfo.Length) bytes)"
    Write-Output "  state     : $(if ($resolvedState) { $resolvedState } else { '(none)' })"
    Write-Output "  state sha : $stateHash"
    Write-Output "  observer  : $resolvedLua"
    Write-Output "  driver    : $resolvedDriver"
    Write-Output "  mGBA      : $resolvedMGB ($mgbVersion)"
    Write-Output "  budget    : observer $MaxFrames frames, driver $DriveFrames frames"
    Write-Output "  route     : $Route"
    Write-Output "  run dir   : $runDir (would be created)"
    return
}

New-Item -ItemType Directory -Path $runDir -Force | Out-Null

$romCopy = Join-Path $runDir 'image.gba'
Copy-Item -LiteralPath $resolvedRom -Destination $romCopy
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $romCopy).Hash -ne $romHashBefore) {
    throw 'Private ROM copy hash mismatch'
}

$workingState = $null
if ($resolvedState) {
    $workingState = Join-Path $runDir 'working-state.ss1'
    Copy-Item -LiteralPath $resolvedState -Destination $workingState
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $workingState).Hash -ne $stateHash) {
        throw 'Savestate copy hash mismatch'
    }
}

$marker = Join-Path $runDir 'marker.txt'
$ready = Join-Path $runDir 'lua-ready.txt'
$saveDir = Join-Path $runDir 'savegame'
New-Item -ItemType Directory -Path $saveDir -Force | Out-Null

@{
    label               = $Label
    canonical_rom_path  = $resolvedRom
    canonical_rom_sha   = $romHashBefore
    image_bytes         = $romInfo.Length
    private_rom_copy    = $romCopy
    state_source_path   = $resolvedState
    state_source_sha256 = $stateHash
    working_state       = $workingState
    lua_path            = $resolvedLua
    driver_path         = $resolvedDriver
    mgba_path           = $resolvedMGB
    mgba_version        = $mgbVersion
    max_frames          = $MaxFrames
    drive_frames        = $DriveFrames
    route               = $Route
    run_dir             = $runDir
} | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $runDir 'inputs.json') -Encoding utf8

$env:DBZ002B_MAX_FRAMES = [string]$MaxFrames
$env:DBZ002B_DRIVE_FRAMES = [string]$DriveFrames
$env:DBZ002B_ROUTE = $Route
$env:LOG1_MGBA_ROM_SHA256 = $romHashBefore.ToLowerInvariant()
$env:DBZ002B_ROM_SIZE = [string]$romInfo.Length
$canonicalSha = '940AD5F01DB4465B8877DFE739510CBF34F4EA3D390F3DF13519808BC36F059E'
if ($romHashBefore -ne $canonicalSha) {
    $env:DBZ002B_DERIVATIVE_SHA256 = $romHashBefore.ToLowerInvariant()
} else {
    Remove-Item Env:\DBZ002B_DERIVATIVE_SHA256 -ErrorAction SilentlyContinue
}
$env:LOG1_MGBA_NO_EXTRA_SCRIPT = '1'

. (Join-Path $PSScriptRoot 'mgba_session.ps1')
$session = @{
    MGBPath            = $resolvedMGB
    RomPath            = $romCopy
    LuaPath            = $resolvedLua
    ReadyPath          = $ready
    MarkerPath         = $marker
    RunDir             = $runDir
    RequiredMGBVersion = $RequiredMGBVersion
    ExpectedRomSha256  = $expected
    PostCommand        = ('dofile([[' + ($resolvedDriver -replace '\\', '/') + ']])')
    ArgumentList       = @('-C', ('savegamePath=' + $saveDir), '-C', 'videoSync=0', '-C', 'audioSync=0')
}
if ($workingState) { $session.StatePath = $workingState }
$process = Start-MgbaSession @session

$canonicalAfter = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedRom).Hash

Write-Output 'SESSION LIVE - bounded, ends itself at the observer frame budget'
Write-Output "  label     : $Label"
Write-Output "  mGBA pid  : $($process.Id)"
Write-Output "  run dir   : $runDir"
Write-Output "  rom sha   : $romHashBefore (copy), source after launch: $canonicalAfter"
