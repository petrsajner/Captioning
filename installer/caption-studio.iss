#ifndef AppVersion
  #error Build with scripts\build.ps1; it passes /DAppVersion from captioning/__init__.py.
#endif
[Setup]
AppId={{3893EE78-D939-4A0B-97C2-131E58B3B430}
AppName=Caption Studio
AppVersion={#AppVersion}
AppPublisher=Caption Studio
DefaultDirName={localappdata}\Programs\Caption Studio
DefaultGroupName=Caption Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=Caption-Studio-Setup-{#AppVersion}-Windows-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\ui\caption-studio.ico
UninstallDisplayIcon={app}\CaptionStudio.exe
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
LanguageDetectionMethod=none

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl,locales\cs.isl"

[CustomMessages]
english.DesktopIcon=Create a desktop shortcut
english.Shortcuts=Shortcuts:
english.LaunchApp=Launch Caption Studio and set up a model
english.UninstallApp=Uninstall Caption Studio
english.AppLanguage=en
english.InstallingWebView2=Installing Microsoft Edge WebView2 Runtime for the application window...

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:Shortcuts}"; Flags: unchecked

[InstallDelete]
; The bundle is always shipped complete; remove the previous one so no stale files remain.
; User data in {app}\data is never touched.
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\licenses"

[Files]
Source: "..\dist\CaptionStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
; The window needs Microsoft Edge WebView2 Runtime; a clean Windows 10 may lack it. The bootstrapper
; downloads and installs it, per user without admin rights. Without it the app opens in the browser.
Source: "redist\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: NeedsWebView2
Source: "..\THIRD_PARTY.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Caption Studio"; Filename: "{app}\CaptionStudio.exe"; WorkingDir: "{app}"; IconFilename: "{app}\_internal\ui\caption-studio.ico"
Name: "{group}\{cm:UninstallApp}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Caption Studio"; Filename: "{app}\CaptionStudio.exe"; WorkingDir: "{app}"; IconFilename: "{app}\_internal\ui\caption-studio.ico"; Tasks: desktopicon

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "{cm:InstallingWebView2}"; Flags: waituntilterminated; Check: NeedsWebView2
Filename: "{app}\CaptionStudio.exe"; Parameters: "--ui-language {cm:AppLanguage}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

; User settings, models and datasets survive uninstall; no UninstallDelete on data.

[Code]
const
  WebView2Client = '\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

{ Microsoft's documented check: the runtime's version under the machine or the user key. }
function WebView2Installed(RootKey: Integer; SubKey: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(RootKey, SubKey, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

function NeedsWebView2: Boolean;
begin
  Result := not (WebView2Installed(HKLM, 'SOFTWARE\WOW6432Node' + WebView2Client)
    or WebView2Installed(HKCU, 'Software' + WebView2Client));
end;
