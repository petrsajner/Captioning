#define AppVersion "0.1.7"
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

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:Shortcuts}"; Flags: unchecked

[Files]
Source: "..\dist\CaptionStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Caption Studio"; Filename: "{app}\CaptionStudio.exe"; WorkingDir: "{app}"; IconFilename: "{app}\_internal\ui\caption-studio.ico"
Name: "{group}\{cm:UninstallApp}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Caption Studio"; Filename: "{app}\CaptionStudio.exe"; WorkingDir: "{app}"; IconFilename: "{app}\_internal\ui\caption-studio.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\CaptionStudio.exe"; Parameters: "--ui-language {cm:AppLanguage}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

; User settings, models and datasets survive uninstall; no UninstallDelete on data.
