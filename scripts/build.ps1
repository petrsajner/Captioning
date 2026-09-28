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
# PyInstaller deletes dist\CaptionStudio; a data folder there would be real user data.
if (Test-Path -LiteralPath 'dist\CaptionStudio\data') { throw 'dist\CaptionStudio\data exists. Move that user data elsewhere before building.' }
& $pythonPath 'scripts\licenses.py'
if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
& $pythonPath -m PyInstaller --noconfirm --clean --windowed --onedir --name CaptionStudio --icon 'ui\caption-studio.ico' --add-data 'ui;ui' --collect-all webview --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.protocols.websockets.auto --hidden-import uvicorn.lifespan.on --exclude-module pydantic.mypy --exclude-module mypy app.py
if ($LASTEXITCODE -ne 0) { throw 'Application build failed.' }
# Development tools in .venv must never ship; pydantic's optional mypy plugin would pull mypy in.
$bundledTools = 'mypy', 'ruff', 'pytest', '_pytest', 'PyInstaller' | Where-Object { Test-Path -LiteralPath "dist\CaptionStudio\_internal\$_" }
if ($bundledTools) { throw "Development tools were bundled: $($bundledTools -join ', ')" }
# llama.cpp needs the Visual C++ runtime, which a clean Windows lacks; the app copies these next to
# llama-server.exe when it extracts the runtime (captioning/runtime.py). Its CUDA build needs 14.44+.
$vcRuntime = 'dist\CaptionStudio\_internal\vcredist'
New-Item -ItemType Directory -Force -Path $vcRuntime | Out-Null
foreach ($dll in 'msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll') {
    $source = Join-Path "$env:SystemRoot\System32" $dll
    if (-not (Test-Path -LiteralPath $source)) { throw "Building needs the Visual C++ 2015-2022 x64 runtime: $dll is missing." }
    $info = (Get-Item -LiteralPath $source).VersionInfo
    if ([version]('{0}.{1}' -f $info.FileMajorPart, $info.FileMinorPart) -lt [version]'14.44') {
        throw "$dll is version $($info.FileVersion); llama.cpp needs 14.44 or newer. Update the Visual C++ runtime."
    }
    Copy-Item -LiteralPath $source -Destination $vcRuntime -Force
}
Copy-Item -LiteralPath 'output\licenses' -Destination 'dist\CaptionStudio\licenses' -Recurse -Force
# The user manuals ship with the application: Start menu shortcuts in the installer, manuals\ in the ZIP.
node 'scripts\manual\build.mjs'
if ($LASTEXITCODE -ne 0) { throw 'User manual build failed.' }
$manuals = 'dist\CaptionStudio\manuals'
New-Item -ItemType Directory -Force -Path $manuals | Out-Null
foreach ($language in 'en', 'cs') {
    $manual = "dist\Caption-Studio-Manual-$version-$language.pdf"
    Copy-Item -LiteralPath $manual -Destination (Join-Path $manuals "Caption-Studio-Manual-$($language.ToUpperInvariant()).pdf") -Force
}
$candidates = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe")
$isccPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $isccPath) { throw 'Building the installer requires Inno Setup 6.' }
& $isccPath "/DAppVersion=$version" 'installer\caption-studio.iss'
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
Copy-Item -LiteralPath 'README.md','THIRD_PARTY.md' -Destination 'dist\CaptionStudio'
Compress-Archive -LiteralPath 'dist\CaptionStudio' -DestinationPath "dist\Caption-Studio-$version-Windows-x64-Portable.zip" -Force
Get-FileHash -Algorithm SHA256 -LiteralPath "dist\Caption-Studio-Setup-$version-Windows-x64.exe","dist\Caption-Studio-$version-Windows-x64-Portable.zip" | ForEach-Object { '{0}  {1}' -f $_.Hash.ToLowerInvariant(), (Split-Path -Leaf $_.Path) } | Set-Content -Encoding utf8 'dist\SHA256SUMS.txt'
