[CmdletBinding()]
param(
    [string] $DistDir = 'build/packaged',
    [string] $BuildName = 'DragonByte Z',
    [string] $CanonicalRom = "roms/Dragon Ball Z - Buu's Fury (U).gba",
    [string] $WorkDir = (Join-Path $env:TEMP 'dragonbyte-z-packaged-smoke'),
    [int] $PlaySeconds = 0
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot

$exe = Join-Path (Join-Path (Join-Path $repo $DistDir) $BuildName) "$BuildName.exe"
if (-not (Test-Path -LiteralPath $exe)) { throw "no packaged executable at $exe - run: pwsh scripts/build-dragonbyte-z.ps1 -Clean" }
if (-not (Test-Path -LiteralPath $CanonicalRom)) { throw "ROM not found at $CanonicalRom" }

if (Test-Path -LiteralPath $WorkDir) {
    Get-ChildItem -LiteralPath $WorkDir -Recurse -File | Remove-Item -Force
}
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
$rom = Join-Path $WorkDir 'private-base.gba'
Copy-Item -LiteralPath $CanonicalRom -Destination $rom
$before = (Get-FileHash -LiteralPath $rom -Algorithm SHA256).Hash
$report = Join-Path $WorkDir 'report.json'

$arguments = @('--selftest', "`"$report`"", '--rom', "`"$rom`"", '--workdir', "`"$WorkDir`"", '--play-seconds', $PlaySeconds)
$process = Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $WorkDir -Wait -PassThru
if (-not (Test-Path -LiteralPath $report)) { throw "the packaged application wrote no report (exit $($process.ExitCode))" }

$result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
foreach ($step in $result.steps) {
    Write-Host ("  {0,-6} {1}" -f $(if ($step.passed) { 'PASS' } else { 'FAIL' }), $step.step)
}
if ((Get-FileHash -LiteralPath $rom -Algorithm SHA256).Hash -ne $before) { throw 'the base ROM changed during the smoke' }
if ($process.ExitCode -ne 0 -or -not $result.passed) { throw "the packaged authoring loop failed; see $report" }

Write-Host ''
Write-Host 'PACKAGED LOOP OK'
Write-Host "  executable  : $exe"
Write-Host "  sha256      : $((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash)"
Write-Host "  window      : $($result.title)"
Write-Host "  built rom   : $($result.output)"
Write-Host "  screenshots : $(Join-Path $WorkDir 'screenshots')"
