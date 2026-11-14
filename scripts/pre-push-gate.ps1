[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$Python,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Sha
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$GitDir = (& git -C $Root rev-parse --git-dir).Trim()
if (-not [System.IO.Path]::IsPathRooted($GitDir)) { $GitDir = Join-Path $Root $GitDir }
$Head = (& git -C $Root rev-parse HEAD).Trim()
$StampDir = Join-Path $GitDir 'pre-push-gate'
$Stamp = Join-Path $StampDir $Head
function Test-Dirty { [bool](& git -C $Root status --porcelain --untracked-files=no) }

$Pushed = @($Sha | Where-Object { $_ -and $_ -notmatch '^0+$' } | Select-Object -Unique)
if ($Sha.Count -gt 0 -and $Pushed.Count -eq 0) {
    Write-Host 'pre-push-gate: only branch deletions are pushed; nothing to verify'
    exit 0
}

if ($Pushed.Count -gt 0) {
    $RunHead = $false
    foreach ($Commit in $Pushed) {
        if (Test-Path -LiteralPath (Join-Path $StampDir $Commit) -PathType Leaf) {
            Write-Host "pre-push-gate: $Commit already passed; verified by its stamp"
            continue
        }
        if ($Commit -ne $Head) {
            Write-Host "pre-push-gate: REFUSED: pushed commit $Commit is not the verified HEAD $Head and has no gate stamp; check it out and push from there"
            exit 1
        }
        if (Test-Dirty) {
            Write-Host "pre-push-gate: REFUSED: pushed commit $Commit is HEAD but tracked files are modified, so the tested tree would not be the pushed commit"
            exit 1
        }
        $RunHead = $true
    }
    if (-not $RunHead) { exit 0 }
} elseif (Test-Path -LiteralPath $Stamp -PathType Leaf) {
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

if ((Test-Dirty) -or (& git -C $Root rev-parse HEAD).Trim() -ne $Head) {
    Write-Host "pre-push-gate: PASS for $Head, but the tree changed under the run, so no stamp was written"
    exit $(if ($Pushed.Count -gt 0) { 1 } else { 0 })
}

New-Item -ItemType Directory -Force -Path $StampDir | Out-Null
Set-Content -LiteralPath $Stamp -Value (Get-Date -Format o)
Write-Host "pre-push-gate: PASS for $Head; stamp $Stamp"
exit 0
