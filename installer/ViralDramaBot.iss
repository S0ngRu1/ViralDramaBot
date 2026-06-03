; ViralDramaBot Windows 安装包（需先执行 build-exe.bat 或 build-installer.bat 生成 dist\ViralDramaBot）

#define MyAppName "ViralDramaBot"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "ViralDramaBot"
#define MyAppExeName "ViralDramaBot.exe"
#define MyAppSource "..\dist\ViralDramaBot"

[Setup]
AppId={{8F3E2A1B-9C4D-5E6F-A7B8-9D0E1F2A3B4C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; 默认装到「Program Files」；向导中可选「仅为当前用户安装」到本地目录（无需管理员）
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=ViralDramaBot-Setup
SetupIconFile=..\frontend\logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
; Inno Setup 6.7+ 官方包未自带简体中文，使用仓库内社区翻译文件
Name: "chinesesimplified"; MessagesFile: "languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:"; Flags: checkedonce

[Files]
Source: "{#MyAppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
; 管理员安装 → 公共桌面；仅为当前用户安装 → 当前用户桌面
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Check: IsAdminInstallMode
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Check: not IsAdminInstallMode

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

; 卸载时不删除 %%APPDATA%%\ViralDramaBot（用户数据与日志保留）
