# Build portable SeePhoto (onedir — fast startup)
# Output: dist\SeePhoto\  folder — copy the whole folder to use

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = "py -3.11"
try {
    & py -3.11 -c "pass" 2>$null
    if ($LASTEXITCODE -ne 0) { $py = "python" }
} catch {
    $py = "python"
}

Write-Host "Installing dependencies ($py)..."
Invoke-Expression "$py -m pip install -r requirements.txt -q"

Write-Host "Building SeePhoto (onedir, faster startup)..."
Invoke-Expression "$py -m PyInstaller seephoto.spec --noconfirm --clean"

$outDir = Join-Path $PSScriptRoot "dist\SeePhoto"
$exe = Join-Path $outDir "SeePhoto.exe"
if (Test-Path $exe) {
    $size = [math]::Round((Get-ChildItem $outDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
    Write-Host ""
    Write-Host "Done: $exe" -ForegroundColor Green
    Write-Host "Folder size: about $size MB — copy entire 'SeePhoto' folder anywhere."
    Write-Host "Run: dist\SeePhoto\SeePhoto.exe"
} else {
    Write-Error "Build failed: $exe not found"
}
