param([string]$Python)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$GitDir = (& git -C $Root rev-parse --git-dir).Trim()
if (-not [System.IO.Path]::IsPathRooted($GitDir)) { $GitDir = Join-Path $Root $GitDir }
$Head = (& git -C $Root rev-parse HEAD).Trim()
$Stamp = Join-Path (Join-Path $GitDir 'pre-push-gate') $Head

if (Test-Path -LiteralPath $Stamp -PathType Leaf) {
    Write-Host "pre-push-gate: $Head already passed; skipped (stamp $Stamp)"
    exit 0
}

if (-not $Python) {
    $Python = Join-Path $Root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { $Python = 'python' }
}

Push-Location $Root
try {
    & $Python -m pytest tests/unit/test_local_ci_script.py tests/unit/test_pre_merge_check.py tests/unit/test_hardcoded_address_census.py tests/unit/test_mgba_launch_coverage.py -q
    $Tests = $LASTEXITCODE
    & $Python -m tools.quality.architecture
    $Architecture = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($Tests -ne 0 -or $Architecture -ne 0) {
    Write-Host "pre-push-gate: FAIL for $Head (meta tests exit $Tests, architecture exit $Architecture)"
    exit 1
}

if (& git -C $Root status --porcelain --untracked-files=no) {
    Write-Host "pre-push-gate: PASS for $Head, but tracked files are modified, so no stamp was written"
    exit 0
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Stamp) | Out-Null
Set-Content -LiteralPath $Stamp -Value (Get-Date -Format o)
Write-Host "pre-push-gate: PASS for $Head; stamp $Stamp"
exit 0
