param(
    [string]$Configuration = "Release",
    [string]$Runtime = "win-x64"
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$repoRoot = Split-Path -Parent $root
$dist = Join-Path $root "dist"
$source = Join-Path $dist $Runtime
$packageDir = Join-Path $dist "package-$Runtime"
$zip = Join-Path $dist "cs2mb-sri-$Runtime.zip"

& (Join-Path $root "build.ps1") -Configuration $Configuration -Runtime $Runtime

if (Test-Path -LiteralPath $packageDir) {
    Remove-Item -LiteralPath $packageDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null

Copy-Item -LiteralPath (Join-Path $source "cs2mb-sri.exe") -Destination $packageDir
Copy-Item -LiteralPath (Join-Path $root "THIRD_PARTY_NOTICES.md") -Destination $packageDir
Copy-Item -LiteralPath (Join-Path $repoRoot "LICENSE") -Destination $packageDir

$exe = Join-Path $packageDir "cs2mb-sri.exe"
$exeHash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
$sums = Join-Path $packageDir "SHA256SUMS.txt"
"$exeHash  cs2mb-sri.exe" | Set-Content -LiteralPath $sums -Encoding ASCII

if (Test-Path -LiteralPath $zip) {
    Remove-Item -LiteralPath $zip -Force
}
Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $zip -CompressionLevel Optimal
$zipHash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()

@(
    "$exeHash  cs2mb-sri.exe"
    "$zipHash  $(Split-Path -Leaf $zip)"
) | Set-Content -LiteralPath (Join-Path $dist "SHA256SUMS.txt") -Encoding ASCII

Write-Host "Wrote $zip"
Write-Host "SHA-256 $zipHash"
