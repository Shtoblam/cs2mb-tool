param(
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtime = Join-Path $root "runtime\python.exe"
$sri = Join-Path $root "tools\bin\sri\cs2mb-sri.exe"
$server = Join-Path $root "app\server.py"
$url = "http://127.0.0.1:$Port/"

if (-not (Test-Path -LiteralPath $server -PathType Leaf)) {
    Write-Error "CS2MB application files are missing: $server"
    exit 1
}
if (-not (Test-Path -LiteralPath $sri -PathType Leaf)) {
    Write-Error "SRI is missing: $sri`nExtract the complete CS2MB package or install SRI in tools\bin\sri."
    exit 1
}

if (Test-Path -LiteralPath $runtime -PathType Leaf) {
    $python = $runtime
    & $python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,13) else 1)"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "The packaged Python runtime is not usable."
        exit 1
    }
    $pythonKind = "runtime"
} else {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        & py -3.13 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,13) else 1)"
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Python 3.13 or newer is required."
            exit 1
        }
        $pythonKind = "py"
    } else {
        $pythonPath = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonPath) {
            Write-Error "Python 3.13 was not found. Use the complete CS2MB package or install Python 3.13 x64."
            exit 1
        }
        & $pythonPath.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3,13) else 1)"
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Python 3.13 or newer is required."
            exit 1
        }
        $pythonKind = "python"
        $python = $pythonPath.Source
    }
}

Write-Host ""
Write-Host "CS2 Map Balance v1.0.0-pre.1" -ForegroundColor Red
Write-Host "SRI - Source Resource Inspector" -ForegroundColor Cyan
Write-Host "Local server: $url"
Write-Host "Press Ctrl+C to stop."
Write-Host ""

$sriVersion = & $sri --version
Write-Host "SRI: $sriVersion"

$browserJob = Start-Job -ScriptBlock {
    param($target)
    Start-Sleep -Seconds 2
    Start-Process $target
} -ArgumentList $url
$browserJob | Out-Null

if ($pythonKind -eq "py") {
    & py -3.13 $server --port $Port
} else {
    & $python $server --port $Port
}
