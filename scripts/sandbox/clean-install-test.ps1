# Clean-Windows test of the Caption Studio installer; runs inside Windows Sandbox.
# Started by scripts/sandbox_test.py, which maps the input folder (installer, media, config.json)
# read-only and a results folder that this script fills with summary.json, logs and screenshots.
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
# The test keeps its own files in one folder, off the desktop; the app installs where it belongs.
$work = 'C:\CaptionStudioTest'
$in = Join-Path $work 'in'
$results = Join-Path $work 'results'
$summary = [ordered]@{}
function Log($message) { "$(Get-Date -Format 'HH:mm:ss') $message" | Out-File -FilePath (Join-Path $results 'log.txt') -Append -Encoding utf8 }
function WebView2Version {
    $client = 'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
    foreach ($key in "HKLM:\SOFTWARE\WOW6432Node\$client", "HKCU:\Software\$client") {
        $pv = (Get-ItemProperty -Path $key -ErrorAction SilentlyContinue).pv
        if ($pv -and $pv -ne '0.0.0.0') { return "$pv ($key)" }
    }
    return 'none'
}
function Screenshot($name) {
    Add-Type -AssemblyName System.Windows.Forms, System.Drawing
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $bitmap.Save((Join-Path $results $name))
    $graphics.Dispose(); $bitmap.Dispose()
}

Start-Sleep -Seconds 5
Log 'start'
# 1. The clean system.
$os = Get-CimInstance Win32_OperatingSystem
$summary.os = "$($os.Caption) $($os.Version)"
$summary.vc_runtime_in_system32 = [ordered]@{}
foreach ($dll in 'msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll') {
    $summary.vc_runtime_in_system32[$dll] = Test-Path (Join-Path "$env:SystemRoot\System32" $dll)
}
$summary.webview2_before = WebView2Version
$summary.dotnet4_release = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full' -ErrorAction SilentlyContinue).Release
$summary.python_on_path = [bool](Get-Command python -ErrorAction SilentlyContinue)
Log ($summary | ConvertTo-Json -Compress)

# 2. Silent install, as a user without admin rights would run it.
$setup = Get-ChildItem $in -Filter 'Caption-Studio-Setup-*.exe' | Select-Object -First 1
$started = Get-Date
$process = Start-Process -FilePath $setup.FullName -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$results\install.log`"" -Wait -PassThru
$summary.installer = $setup.Name
$summary.installer_exit = $process.ExitCode
$summary.installer_seconds = [int]((Get-Date) - $started).TotalSeconds
$summary.webview2_after = WebView2Version
$summary.webview2_bootstrapper_ran = [bool](Select-String -Path "$results\install.log" -Pattern 'MicrosoftEdgeWebview2Setup' -Quiet)
$app = Join-Path $env:LOCALAPPDATA 'Programs\Caption Studio'
$summary.installed = Test-Path (Join-Path $app 'CaptionStudio.exe')
Log "installed: $($summary.installed), exit $($summary.installer_exit)"
# The user manuals and their Start menu shortcuts.
$summary.manuals = @('EN', 'CS' | Where-Object { Test-Path (Join-Path $app "manuals\Caption-Studio-Manual-$_.pdf") }).Count
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Caption Studio'
$summary.start_menu = @(Get-ChildItem $startMenu -Filter '*.lnk' -ErrorAction SilentlyContinue | ForEach-Object { $_.BaseName })

# 3. Start the app the normal way, with its window.
Start-Process -FilePath (Join-Path $app 'CaptionStudio.exe')
$launch = Join-Path $app 'data\launch.json'
for ($i = 0; $i -lt 120 -and -not (Test-Path $launch); $i++) { Start-Sleep -Milliseconds 500 }
$summary.app_started = Test-Path $launch
Start-Sleep -Seconds 20
Screenshot 'window.png'
$summary.app_process_running = [bool](Get-Process CaptionStudio -ErrorAction SilentlyContinue)
$summary.webview2_processes = @(Get-Process msedgewebview2 -ErrorAction SilentlyContinue).Count
$appLog = Join-Path $app 'data\app.log'
if (Test-Path $appLog) { Copy-Item $appLog (Join-Path $results 'app.log') }
Log "app started: $($summary.app_started), webview2 processes: $($summary.webview2_processes)"

# 4. The app's own API: import photos and a clip, thumbnails, clip frames, a saved caption.
try {
    $url = (Get-Content $launch -Raw | ConvertFrom-Json).url
    $origin = $url.Split('?')[0].TrimEnd('/')
    $null = Invoke-WebRequest -Uri $url -UseBasicParsing -SessionVariable web
    $headers = @{ 'X-Caption-Client' = '1'; 'Origin' = $origin }
    $media = Join-Path $work 'media'
    Copy-Item (Join-Path $in 'media') $media -Recurse -Force
    $body = @{ folder = $media; recursive = $false; append = $false } | ConvertTo-Json
    $null = Invoke-WebRequest -Uri "$origin/api/import" -Method Post -Body $body -ContentType 'application/json' -Headers $headers -WebSession $web -UseBasicParsing
    $state = Invoke-RestMethod -Uri "$origin/api/state" -WebSession $web -Headers $headers
    $summary.version = $state.version
    $summary.imported = @($state.rows).Count
    $photo = @($state.rows | Where-Object { $_.kind -eq 'image' })[0]
    $clip = @($state.rows | Where-Object { $_.kind -eq 'clip' })[0]
    $thumb = Invoke-WebRequest -Uri "$origin/api/image/$($photo.id)" -WebSession $web -Headers $headers -UseBasicParsing
    $summary.photo_thumbnail = $thumb.Headers['Content-Type']
    $frames = Invoke-RestMethod -Uri "$origin/api/clip-frames/$($clip.id)" -WebSession $web -Headers $headers
    $summary.clip_frames = @($frames.times).Count
    $summary.clip_info = "$($clip.clip.width)x$($clip.clip.height) $($clip.clip.fps) fps $($clip.clip.frames) frames"
    $caption = @{ text = 'Zorbo, a puzzle cube, rests on a windowsill.'; output = 'normal' } | ConvertTo-Json
    $null = Invoke-WebRequest -Uri "$origin/api/caption/$($photo.id)" -Method Put -Body $caption -ContentType 'application/json' -Headers $headers -WebSession $web -UseBasicParsing
    $saved = [IO.Path]::ChangeExtension($photo.path, '.txt')
    $summary.caption_saved = (Test-Path $saved) -and ((Get-Content $saved -Raw).Trim() -eq 'Zorbo, a puzzle cube, rests on a windowsill.')
    $prompt = Invoke-RestMethod -Uri "$origin/api/prompt" -Method Post -Body (@{ preset = 'object'; output_format = 'wan'; trigger = 'Zorbo' } | ConvertTo-Json) -ContentType 'application/json' -Headers $headers -WebSession $web
    $summary.prompt_for_wan = [bool]($prompt.prompt -match '<object>')
} catch {
    $summary.api_error = $_.Exception.Message
}
Log 'api done'

# 5. llama.cpp on this clean system: without and with the Visual C++ runtime the app ships.
try {
    $zip = Join-Path $work 'llama-cpu.zip'
    $config = Get-Content (Join-Path $in 'config.json') -Raw | ConvertFrom-Json
    Invoke-WebRequest -Uri $config.llama_cpu_url -OutFile $zip -UseBasicParsing
    $llama = Join-Path $work 'llama'
    Expand-Archive $zip $llama -Force
    $server = Get-ChildItem $llama -Recurse -Filter 'llama-server.exe' | Select-Object -First 1
    $run = Start-Process -FilePath $server.FullName -ArgumentList '--version' -Wait -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $results 'llama-without.txt') -RedirectStandardError (Join-Path $results 'llama-without-err.txt')
    $summary.llama_without_vc_runtime_exit = $run.ExitCode
    Copy-Item (Join-Path $app '_internal\vcredist\*.dll') $server.DirectoryName
    $run = Start-Process -FilePath $server.FullName -ArgumentList '--version' -Wait -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $results 'llama-with.txt') -RedirectStandardError (Join-Path $results 'llama-with-err.txt')
    $summary.llama_with_bundled_vc_runtime_exit = $run.ExitCode
} catch {
    $summary.llama_error = $_.Exception.Message
}
Log 'llama done'

Screenshot 'end.png'
$summary | ConvertTo-Json -Depth 4 | Out-File (Join-Path $results 'summary.json') -Encoding utf8
Log 'finished'
