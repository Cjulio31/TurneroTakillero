; Instalador de Turnos Desktop (Inno Setup 6). Se compila con packaging\build.ps1, que pasa
; /DAppVersion=<constants.APP_VERSION>. Requiere dist\TurnosDesktop (salida de PyInstaller).
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; AppId identifica la app entre versiones: NO cambiarlo (permite actualizar sobre la anterior).
AppId={{6F1D3B7A-4C52-4E0B-9A57-2B8C1E5D90A3}
AppName=Turnos Desktop
AppVersion={#AppVersion}
AppPublisher=Turnos
DefaultDirName={autopf}\TurnosDesktop
DefaultGroupName=Turnos Desktop
OutputDir=Output
OutputBaseFilename=TurnosDesktopSetup
SetupIconFile=..\resources\icons\app.ico
UninstallDisplayIcon={app}\TurnosDesktop.exe
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
; Instalación por usuario (sin administrador): los datos viven en %LOCALAPPDATA%\TurnosDesktop
; y "iniciar con Windows" se registra en HKCU.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes
RestartApplications=no
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "autostart"; Description: "Iniciar Turnos Desktop al iniciar Windows"; Flags: checkedonce
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; Flags: unchecked

[Files]
Source: "..\dist\TurnosDesktop\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Turnos Desktop"; Filename: "{app}\TurnosDesktop.exe"
Name: "{group}\Desinstalar Turnos Desktop"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Turnos Desktop"; Filename: "{app}\TurnosDesktop.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "TurnosDesktop"; ValueData: """{app}\TurnosDesktop.exe"""; \
  Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\TurnosDesktop.exe"; Description: "Abrir Turnos Desktop"; \
  Flags: nowait postinstall skipifsilent

; Los datos del usuario (%LOCALAPPDATA%\TurnosDesktop: base de datos y logs) NO se borran al
; desinstalar: contienen turnos que pueden estar pendientes.
