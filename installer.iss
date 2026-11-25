#ifndef MyAppVersion
  #define MyAppVersion "1.3.0"
#endif
#ifndef SourceDir
  #define SourceDir "."
#endif

[Setup]
AppId={{8F6C2B51-9E2D-4C84-A6D0-1F8E3D95B7A1}
AppName=QuickOCR
AppVersion={#MyAppVersion}
AppPublisher=Abolfazl Shahi (@pythash)
AppPublisherURL=https://github.com/Abolfazlshahi/QuickOCR
DefaultDirName={localappdata}\Programs\QuickOCR
DefaultGroupName=QuickOCR
PrivilegesRequired=lowest
OutputDir=.
OutputBaseFilename=QuickOCR-v{#MyAppVersion}-Windows-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\QuickOCR.exe
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
CloseApplicationsFilter=QuickOCR.exe
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\QuickOCR"; Filename: "{app}\QuickOCR.exe"; IconFilename: "{app}\QuickOCR.exe"
Name: "{autodesktop}\QuickOCR"; Filename: "{app}\QuickOCR.exe"; IconFilename: "{app}\QuickOCR.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\QuickOCR.exe"; Description: "{cm:LaunchProgram,QuickOCR}"; Flags: nowait postinstall skipifsilent
