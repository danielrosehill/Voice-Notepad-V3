; Voice Notepad Windows Installer
; Inno Setup Script
;
; This script creates a Windows installer for Voice Notepad.
; It is used by the GitHub Actions workflow.
;
; SourceDir points to repository root (two levels up from this script)

#define MyAppName "Voice Notepad"
#define MyAppVersion GetEnv('APP_VERSION')
#define MyAppPublisher "Daniel Rosehill"
#define MyAppURL "https://github.com/danielrosehill/Voice-Notepad"
#define MyAppExeName "Voice Notepad.exe"

[Setup]
; App identity
AppId={{8F3C2E5A-7B4D-4A1F-9E8C-6D5F3B2A1C0D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases

; Set source directory to repository root
SourceDir=..\..

; Installer settings
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=dist
OutputBaseFilename=Voice-Notepad-{#MyAppVersion}-windows-x64-setup
SetupIconFile=assets\voice-notepad.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; Privileges - no admin required for per-user install
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Uninstall settings
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

; Architecture
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Main application files from PyInstaller output
Source: "dist\Voice Notepad\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Add version info to Add/Remove Programs
procedure InitializeWizard;
begin
  WizardForm.LicenseAcceptedRadio.Checked := True;
end;
