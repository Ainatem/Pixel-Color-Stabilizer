$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
python -m pip install '.[build]'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
python -m PyInstaller --noconfirm --clean --windowed --onedir --name PixelColorStabilizer --collect-all scipy --copy-metadata pillow --copy-metadata numpy --copy-metadata scipy --paths . scripts/gui_entry.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$reportPath = Join-Path (Get-Location) 'build/portable-self-test.json'
if (Test-Path -LiteralPath $reportPath) { Remove-Item -LiteralPath $reportPath }
$testProcess = Start-Process -FilePath (Join-Path (Get-Location) 'dist/PixelColorStabilizer/PixelColorStabilizer.exe') -ArgumentList @('--self-test', ('"' + $reportPath + '"')) -WindowStyle Hidden -Wait -PassThru
if ($testProcess.ExitCode -ne 0 -or !(Test-Path -LiteralPath $reportPath)) { throw 'Portable executable smoke test failed' }
Copy-Item -LiteralPath LICENSE,README.md,README.en.md,THIRD_PARTY.md,VALIDATION.md -Destination dist/PixelColorStabilizer
python scripts/collect_licenses.py dist/PixelColorStabilizer/third_party_licenses
if ($LASTEXITCODE -ne 0) { throw 'License collection failed' }
Compress-Archive -Path dist/PixelColorStabilizer -DestinationPath dist/PixelColorStabilizer-windows-x64.zip -Force
