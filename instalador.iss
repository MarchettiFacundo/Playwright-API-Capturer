; Script de Inno Setup para generar el instalador profesional de Playwright API Capturer
; Desarrollado para el proyecto RPA.

[Setup]
; Identificador único de la aplicación (GUID)
AppId={{5D0B26D1-C998-4A3C-93E1-EFE5C13FF15A}
AppName=Playwright API Capturer
AppVersion=1.1.9
AppPublisher=RPA Tools
AppPublisherURL=https://bitbucket.org/
AppSupportURL=https://bitbucket.org/
AppUpdatesURL=https://bitbucket.org/
DefaultDirName={commonpf}\Playwright API Capturer
DefaultGroupName=Playwright API Capturer
DisableProgramGroupPage=yes
; Directorio donde se generará el instalador (dentro de dist/)
OutputDir=dist
OutputBaseFilename=Playwright_API_Capturer_Setup
SetupIconFile=assets\app_icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Requiere elevación de privilegios de administrador para instalar en C:\Program Files
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Archivo ejecutable principal compilado por PyInstaller
Source: "dist\Playwright API Capturer.exe"; DestDir: "{app}"; Flags: ignoreversion
; Icono de la aplicación para los accesos directos
Source: "assets\app_icon.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
; Directorios opcionales de documentación y ejemplos si existen
Source: "docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs onlyifdestfileexists
Source: "ejemplos\*"; DestDir: "{app}\ejemplos"; Flags: ignoreversion recursesubdirs createallsubdirs onlyifdestfileexists

[Icons]
; Acceso directo en el Menú Inicio
Name: "{group}\Playwright API Capturer"; Filename: "{app}\Playwright API Capturer.exe"; IconFilename: "{app}\assets\app_icon.ico"
Name: "{group}\{cm:UninstallProgram,Playwright API Capturer}"; Filename: "{uninstallexe}"
; Acceso directo opcional en el Escritorio
Name: "{autodesktop}\Playwright API Capturer"; Filename: "{app}\Playwright API Capturer.exe"; IconFilename: "{app}\assets\app_icon.ico"; Tasks: desktopicon

[Run]
; Opción para lanzar la aplicación al finalizar el instalador
Filename: "{app}\Playwright API Capturer.exe"; Description: "{cm:LaunchProgram,Playwright API Capturer}"; Flags: nowait postinstall skipifsilent
