; Inno Setup 6 Script for AI-Telefonist
; Production-ready Windows Installer with LZMA2 compression, process termination, and complete DelTree wipe

#define MyAppName "AI-Telefonist"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "AI-Telefonist"
#define MyAppExeName "ai-telefonist.exe"

[Setup]
AppId={{E68F0471-9DB5-4D62-A37F-C8694BF43310}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=AI-Telefonist-Installer
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "dutch"; MessagesFile: "compiler:Languages\Dutch.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Main PyInstaller Lightweight Executable
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Configuration Template
Source: "..\config.example.json"; DestDir: "{app}"; Flags: ignoreversion

; External Model Weights (Packaged at installer root, outside PyInstaller binary)
Source: "..\models\*"; DestDir: "{app}\models"; Flags: ignoreversion recursesubdirs createallsubdirs

; Local llama.cpp Binaries
Source: "..\bin\llama\*"; DestDir: "{app}\bin\llama"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Helper function to silently kill active processes
procedure KillRunningProcesses();
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM ai-telefonist.exe /IM llama-server.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

// Terminate running processes before installation starts
function InitializeSetup(): Boolean;
begin
  KillRunningProcesses();
  Result := True;
end;

// Terminate running processes before uninstallation begins
function InitializeUninstall(): Boolean;
begin
  KillRunningProcesses();
  Result := True;
end;

// Clean uninstallation: wipe all runtime directories, appointments.json, caches, and logs
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDirPath: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppDirPath := ExpandConstant('{app}');
    // Completely wipe application directory
    DelTree(AppDirPath, True, True, True);
  end;
end;
