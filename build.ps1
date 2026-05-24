# Build 易图 — 单 exe 启动器 + AppData 缓存（首次解压，之后快速启动）
# Output: dist\易图.exe

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-Py {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & py -3.11 @Args
    if ($LASTEXITCODE -ne 0) { throw "Python command failed: py -3.11 $($Args -join ' ')" }
}

try {
    & py -3.11 -c "pass" 2>$null
    if ($LASTEXITCODE -ne 0) { throw "py -3.11 not found" }
} catch {
    function Invoke-Py {
        param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
        & python @Args
        if ($LASTEXITCODE -ne 0) { throw "Python command failed" }
    }
}

Write-Host "Installing dependencies..."
Invoke-Py -m pip install -r requirements.txt -q

$version = (Invoke-Py -c "from seephoto import __version__; print(__version__)").Trim()
$buildDir = Join-Path $PSScriptRoot "build"
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
Set-Content -Path (Join-Path $buildDir "VERSION") -Value $version -Encoding UTF8 -NoNewline
Write-Host "Version: $version"

Write-Host "Building app (onedir)..."
Invoke-Py -m PyInstaller seephoto_onedir.spec --noconfirm --clean

$appDir = Join-Path $PSScriptRoot "dist\yitu_app"
$appExe = Get-ChildItem -Path $appDir -Filter "*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $appExe) {
    Write-Error "Build failed: no exe found in dist\yitu_app"
}

Write-Host "Packing yitu_bundle.zip..."
$zipPath = Join-Path $buildDir "yitu_bundle.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $appDir "*") -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host "Building launcher (onefile)..."
Get-Process | Where-Object { $_.Path -like "*\dist\*.exe" -or $_.MainWindowTitle -like "*易图*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 300
Invoke-Py -m PyInstaller launcher.spec --noconfirm --clean

$distDir = Join-Path $PSScriptRoot "dist"
$outExe = Get-ChildItem -Path $distDir -Filter "*.exe" -File -ErrorAction SilentlyContinue |
    Where-Object { $_.DirectoryName -eq $distDir } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if ($outExe) {
    $size = [math]::Round($outExe.Length / 1MB, 1)
    Write-Host ""
    Write-Host "Done: $($outExe.FullName)" -ForegroundColor Green
    Write-Host "Size: about $size MB"
    Write-Host "First run extracts to: %LOCALAPPDATA%\llso\yitu\$version"
    Write-Host "Later runs start from cache (fast)."
} else {
    Write-Error "Build failed: dist\易图.exe not found"
}
