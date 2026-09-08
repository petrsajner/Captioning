$ErrorActionPreference = 'Stop'
$workspacePath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $workspacePath
$pythonPath = Join-Path $workspacePath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Nejprve pripravte .venv pomoci run.bat.' }
& $pythonPath -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Testy selhaly.' }
& $pythonPath 'scripts\licenses.py'
if ($LASTEXITCODE -ne 0) { throw 'Sber licenci selhal.' }
& $pythonPath -m PyInstaller --noconfirm --clean --windowed --onedir --name CaptionStudio --icon 'ui\caption-studio.ico' --add-data 'ui;ui' --collect-all webview --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.protocols.websockets.auto --hidden-import uvicorn.lifespan.on app.py
if ($LASTEXITCODE -ne 0) { throw 'Sestaveni aplikace selhalo.' }
Copy-Item -LiteralPath 'output\licenses' -Destination 'dist\CaptionStudio\licenses' -Recurse -Force
$candidates = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe")
$isccPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $isccPath) { throw 'Pro sestaveni instalatoru je potreba Inno Setup 6.' }
& $isccPath 'installer\caption-studio.iss'
if ($LASTEXITCODE -ne 0) { throw 'Sestaveni instalatoru selhalo.' }
Copy-Item -LiteralPath 'README.md','THIRD_PARTY.md' -Destination 'dist\CaptionStudio'
Compress-Archive -LiteralPath 'dist\CaptionStudio' -DestinationPath 'dist\Caption-Studio-0.1.4-Windows-x64-Portable.zip' -Force
Get-FileHash -Algorithm SHA256 -LiteralPath 'dist\Caption-Studio-Setup-0.1.4-Windows-x64.exe','dist\Caption-Studio-0.1.4-Windows-x64-Portable.zip' | ForEach-Object { '{0}  {1}' -f $_.Hash.ToLowerInvariant(), (Split-Path -Leaf $_.Path) } | Set-Content -Encoding utf8 'dist\SHA256SUMS.txt'
