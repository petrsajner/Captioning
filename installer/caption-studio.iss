#define AppVersion "0.1.2"
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
UninstallDisplayIcon={app}\CaptionStudio.exe
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Vytvořit zástupce na ploše"; GroupDescription: "Zástupci:"; Flags: unchecked

[Files]
Source: "..\dist\CaptionStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Caption Studio"; Filename: "{app}\CaptionStudio.exe"; WorkingDir: "{app}"
Name: "{group}\Odinstalovat Caption Studio"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Caption Studio"; Filename: "{app}\CaptionStudio.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CaptionStudio.exe"; Description: "Spustit Caption Studio a nastavit model"; Flags: nowait postinstall skipifsilent

; User settings, models and datasets survive uninstall; no UninstallDelete on data.
