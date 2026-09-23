$ErrorActionPreference = 'Stop'
$workspacePath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $workspacePath
$pythonPath = Join-Path $workspacePath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create the .venv using run.bat first.' }
# The version is defined only in captioning/__init__.py.
$version = (& $pythonPath -c 'from captioning import __version__; print(__version__)' | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw 'Unable to read the application version.' }
& $pythonPath -m ruff check .
if ($LASTEXITCODE -ne 0) { throw 'Lint failed.' }
& $pythonPath -m ruff format --check .
if ($LASTEXITCODE -ne 0) { throw 'Formatting check failed.' }
& $pythonPath -m mypy
if ($LASTEXITCODE -ne 0) { throw 'Type check failed.' }
& $pythonPath -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'UI checks require Node.js; run npm ci first.' }
npm run --silent format:check
if ($LASTEXITCODE -ne 0) { throw 'UI formatting check failed.' }
npm test --silent
if ($LASTEXITCODE -ne 0) { throw 'UI tests failed.' }
npm run --silent test:ui
if ($LASTEXITCODE -ne 0) { throw 'Browser UI suite failed.' }
& $pythonPath 'scripts\licenses.py'
if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
& $pythonPath -m PyInstaller --noconfirm --clean --windowed --onedir --name CaptionStudio --icon 'ui\caption-studio.ico' --add-data 'ui;ui' --collect-all webview --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.protocols.websockets.auto --hidden-import uvicorn.lifespan.on --exclude-module pydantic.mypy --exclude-module mypy app.py
if ($LASTEXITCODE -ne 0) { throw 'Application build failed.' }
# Development tools in .venv must never ship; pydantic's optional mypy plugin would pull mypy in.
$bundledTools = 'mypy', 'ruff', 'pytest', '_pytest', 'PyInstaller' | Where-Object { Test-Path -LiteralPath "dist\CaptionStudio\_internal\$_" }
if ($bundledTools) { throw "Development tools were bundled: $($bundledTools -join ', ')" }
Copy-Item -LiteralPath 'output\licenses' -Destination 'dist\CaptionStudio\licenses' -Recurse -Force
$candidates = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe")
$isccPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $isccPath) { throw 'Building the installer requires Inno Setup 6.' }
& $isccPath "/DAppVersion=$version" 'installer\caption-studio.iss'
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
Copy-Item -LiteralPath 'README.md','THIRD_PARTY.md' -Destination 'dist\CaptionStudio'
Compress-Archive -LiteralPath 'dist\CaptionStudio' -DestinationPath "dist\Caption-Studio-$version-Windows-x64-Portable.zip" -Force
Get-FileHash -Algorithm SHA256 -LiteralPath "dist\Caption-Studio-Setup-$version-Windows-x64.exe","dist\Caption-Studio-$version-Windows-x64-Portable.zip" | ForEach-Object { '{0}  {1}' -f $_.Hash.ToLowerInvariant(), (Split-Path -Leaf $_.Path) } | Set-Content -Encoding utf8 'dist\SHA256SUMS.txt'
