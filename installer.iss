; ============================================================
; Keithley IV Suite — Inno Setup 6 installer script
;
; Creates a self-installing Windows setup EXE that:
;   - Installs to %ProgramFiles%\Keithley IV Suite\
;   - Creates a Start Menu shortcut
;   - Optionally creates a Desktop shortcut
;   - Registers an Add/Remove Programs entry with uninstaller
;
; PREREQUISITES:
;   1. Run scripts\build_exe.bat first (populates dist\Keithley_IV_Suite\)
;   2. Install Inno Setup 6 from https://jrsoftware.org/isdl.php
;   3. Compile:  ISCC.exe installer.iss
;      (or open this file in the Inno Setup IDE and press F9)
;
; OUTPUT:  release\Keithley_IV_Suite_v2.2.0_Setup.exe
;          (~130 MB self-extracting installer, no dependencies needed)
; ============================================================

#define AppName      "Keithley IV Suite"
#define AppVersion   "2.2.0"
#define AppPublisher "Prashant Srinivasan"
#define AppExeName   "Keithley_IV_Suite.exe"

[Setup]
AppId={{A8F3C2D1-9E4B-4F6A-B7C3-2D1E5F8A9B0C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/prashantUCSB/keithley-iv-suite

; Installation directory
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}

; Output
OutputBaseFilename=Keithley_IV_Suite_v{#AppVersion}_Setup
OutputDir=release

; Compression (lzma2 ultra produces ~45% smaller installer)
Compression=lzma2/ultra64
SolidCompression=yes

; UI
WizardStyle=modern
DisableProgramGroupPage=yes
DisableWelcomePage=no

; Target: 64-bit Windows 10 1903+ (required for consistent Qt6 DPI behavior)
MinVersion=10.0.18362
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Elevation — needs admin to write to %ProgramFiles%
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline

; Uninstaller
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}

; Version info shown in Add/Remove Programs
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; \
  Description: "{cm:CreateDesktopIcon}"; \
  GroupDescription: "{cm:AdditionalIcons}"; \
  Flags: unchecked

[Files]
; Main executable
Source: "dist\Keithley_IV_Suite\{#AppExeName}"; \
  DestDir: "{app}"; \
  Flags: ignoreversion

; All bundled runtime files (Qt, Python, DLLs, etc.)
Source: "dist\Keithley_IV_Suite\_internal\*"; \
  DestDir: "{app}\_internal"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

; Desktop (optional — user must tick the checkbox)
Name: "{commondesktop}\{#AppName}"; \
  Filename: "{app}\{#AppExeName}"; \
  Tasks: desktopicon

[Run]
; Offer to launch after install
Filename: "{app}\{#AppExeName}"; \
  Description: "{cm:LaunchProgram,{#AppName}}"; \
  Flags: nowait postinstall skipifsilent

[Code]
// Check that the dist\ folder was built before trying to compile the installer
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then begin
    // Nothing extra needed — pyvisa-py is bundled, no driver check required.
    // For GPIB instruments, users still need NI-VISA or Keysight IO installed
    // separately; Ethernet/USB-TMC instruments work out of the box.
  end;
end;
