# Run after scripts/build-postboy-advance.ps1 and scripts/smoke-postboy-advance-packaged.ps1.

[CmdletBinding()]
param(
    [string] $DistDir = 'build/packaged',
    [string] $BuildName = 'Postboy Advance',
    [string] $CanonicalRom = "roms/Dragon Ball Z - Buu's Fury (U).gba",
    [string] $ReadmePath = 'docs/postboy/README.txt',
    [switch] $SkipRomProbe
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/randomizer-release.ps1"

$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    $app = Join-Path $DistDir $BuildName
    $exe = Join-Path $app "$BuildName.exe"
    if (-not (Test-Path -LiteralPath $exe)) {
        throw "no packaged build at $exe - run: pwsh scripts/build-postboy-advance.ps1 -Clean"
    }
    if (-not (Test-Path $ReadmePath)) { throw "no README to stage at $ReadmePath" }
    $Version = (& python -m tools.webfoot.release_identity --json | ConvertFrom-Json).product.version
    if ($LASTEXITCODE -ne 0 -or -not $Version) { throw "could not read the product version" }

    $stageRoot = Join-Path $DistDir "$BuildName-release"
    $stage = Join-Path $stageRoot $BuildName
    if (Test-Path -LiteralPath $stageRoot) { Remove-Item -LiteralPath $stageRoot -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null
    Copy-Item -LiteralPath $app -Destination $stage -Recurse
    Copy-Item LICENSE (Join-Path $stage 'LICENSE')
    Copy-Item THIRD-PARTY-NOTICES.md (Join-Path $stage 'THIRD-PARTY-NOTICES.md')
    Copy-Item packaging/licenses (Join-Path $stage 'licenses') -Recurse
    Copy-Item $ReadmePath (Join-Path $stage 'README.txt')
    $staged = @(Get-ChildItem -LiteralPath $stage -File -Recurse)
    Write-Host ("staged {0} file(s) under {1}" -f $staged.Count, $stage)

    $offenders = Assert-RandomizerNoProprietaryContent `
        -Staged $staged `
        -CanonicalRom $CanonicalRom `
        -ExpectedSha256 $script:RandomizerCanonicalSha256 `
        -ExpectedSize $script:RandomizerCanonicalSize `
        -SkipRomProbe:$SkipRomProbe

    if ($offenders.Count -gt 0) {
        throw ("proprietary content in the release package:`n  " + ($offenders -join "`n  "))
    }
    if ($SkipRomProbe) {
        Write-Host 'proprietary-content check: NONE FOUND by the extension and exact-hash checks (ROM byte probe SKIPPED - this is NOT the full check)'
    }
    else {
        Write-Host 'proprietary-content check: NONE'
    }

    $required = @("$BuildName.exe", 'README.txt', 'LICENSE', 'THIRD-PARTY-NOTICES.md', '_internal/tools/webfoot/data/roms.yaml') +
        @(Get-ChildItem packaging/licenses -File | ForEach-Object { "licenses/$($_.Name)" })
    $census = @($stage) + @($required | ForEach-Object { '--require', $_ })
    & python -m tools.quality.package_content @census
    if ($LASTEXITCODE -ne 0) { throw "the package census of $stage failed" }

    # One top-level folder, so "extract and run" keeps the runtime beside the program.
    $zip = Join-Path $DistDir ("{0}-{1}-windows-x64.zip" -f ($BuildName -replace ' ', '-'), $Version)
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
    Compress-Archive -LiteralPath $stage -DestinationPath $zip -CompressionLevel Optimal
    $zipInfo = Get-Item -LiteralPath $zip
    Write-Host ("release {0} ({1:N1} MB)" -f $zipInfo.FullName, ($zipInfo.Length / 1MB))

    $digest = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
    $checksum = "$($zipInfo.FullName).sha256"
    [System.IO.File]::WriteAllText($checksum, "$digest  $($zipInfo.Name)`n")
    Write-Host ("sha256 {0}  {1}" -f $digest, $zipInfo.Name)

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    # .NET resolves relative paths against the process directory, which Push-Location does not move.
    $archive = [System.IO.Compression.ZipFile]::OpenRead($zipInfo.FullName)
    $tops = @($archive.Entries | ForEach-Object { ($_.FullName -split '/')[0] } | Sort-Object -Unique)
    Write-Host ("archive: {0} entries, top level: {1}" -f $archive.Entries.Count, ($tops -join ', '))
    $archive.Dispose()
}
finally {
    Pop-Location
}
