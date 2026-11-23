param(
    [string]$Configuration = "Release",
    [string]$Runtime = "win-x64",
    [switch]$Install
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$project = Join-Path $root "Cs2mb.Source2\Cs2mb.Source2.csproj"
$output = Join-Path $root "dist\$Runtime"

Write-Host "Restoring pinned packages..."
dotnet restore $project -r $Runtime -p:PublishTrimmed=true

Write-Host "Publishing $Configuration/$Runtime..."
dotnet publish $project `
    -c $Configuration `
    -r $Runtime `
    --self-contained true `
    --no-restore `
    -p:PublishSingleFile=true `
    -p:PublishTrimmed=true `
    -p:TrimMode=partial `
    -p:InvariantGlobalization=true `
    -p:DebugType=None `
    -p:DebugSymbols=false `
    -o $output

$exe = Join-Path $output "cs2mb-source2.exe"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "publish did not produce $exe"
}

# The CS2MB commands only decode PHYS and EntityLump. The optional renderer
# natives are not loaded; keep the release directory to the single executable.
Get-ChildItem -LiteralPath $output -File |
    Where-Object { $_.Name -ne "cs2mb-source2.exe" } |
    Remove-Item -Force

$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
$size = (Get-Item -LiteralPath $exe).Length
Write-Host ("Built {0} ({1:N0} bytes)" -f $exe, $size)
Write-Host "SHA-256 $hash"

if ($Install) {
    $repoRoot = Split-Path -Parent $root
    $target = Join-Path $repoRoot "tools\bin\source2"
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Copy-Item -LiteralPath $exe -Destination (Join-Path $target "cs2mb-source2.exe") -Force
    Write-Host "Installed to $target"
}
