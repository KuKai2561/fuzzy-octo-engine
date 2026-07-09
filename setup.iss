; ============================================================
; KuKai 技術提案書作成アプリ  Inno Setup スクリプト
; ============================================================

#define AppName      "KuKai 技術提案書作成アプリ"
#define AppVersion   "1.0.0"
#define AppPublisher "KuKai"
#define AppURL       "https://h-hkukai.com"
#define AppExeName   "launcher_silent.pyw"
#define BuildDir     SourcePath + "_build"
#define InstallDir   "{autopf}\KuKai\GTK"

[Setup]
AppId={{8F3A2C1E-4B7D-4E9F-A2B3-C1D4E5F6A7B8}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={#InstallDir}
DefaultGroupName=KuKai
AllowNoIcons=yes
OutputDir={#SourcePath}Output
OutputBaseFilename=KuKai_技術提案書_Setup
SetupIconFile=
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

; インストーラー自体の外観
WizardImageFile=compiler:WizModernImage-IS.bmp
WizardSmallImageFile=compiler:WizModernSmallImage-IS.bmp

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成する"; GroupDescription: "追加タスク"; Flags: checked

[Files]
; アプリ本体
Source: "{#BuildDir}\KuKai_技術提案書作成.py";  DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\claude_generator.py";        DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\generator.py";               DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\key_manager.py";             DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\reference_manager.py";       DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\excel_exporter.py";          DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\db_manager.py";              DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\launcher_silent.pyw";        DestDir: "{app}"; Flags: ignoreversion

; 組み込みPython（フォルダごと）
Source: "{#BuildDir}\python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
; データ保存フォルダを初期作成
Name: "{app}\data"

[Icons]
; スタートメニュー
Name: "{group}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launcher_silent.pyw"""; WorkingDir: "{app}"; Comment: "技術提案書作成アプリを起動"
Name: "{group}\アンインストール"; Filename: "{uninstallexe}"

; デスクトップショートカット
Name: "{autodesktop}\技術提案書作成"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launcher_silent.pyw"""; WorkingDir: "{app}"; Comment: "技術提案書作成アプリを起動"; Tasks: desktopicon

[Run]
; ─── インストール後に Windows Defender 除外登録 ───────────────
Filename: "powershell.exe"; \
    Parameters: "-ExecutionPolicy Bypass -Command ""Add-MpPreference -ExclusionPath '{app}' -ErrorAction SilentlyContinue"""; \
    Flags: runhidden waituntilterminated; \
    StatusMsg: "セキュリティソフトの除外登録中...（誤検知防止）"

; ─── インストール完了後にアプリを起動するか確認 ──────────────
Filename: "{app}\python\pythonw.exe"; \
    Parameters: """{app}\launcher_silent.pyw"""; \
    WorkingDir: "{app}"; \
    Description: "アプリを今すぐ起動する"; \
    Flags: nowait postinstall skipifsilent

[UninstallRun]
; アンインストール時に Defender 除外を削除
Filename: "powershell.exe"; \
    Parameters: "-ExecutionPolicy Bypass -Command ""Remove-MpPreference -ExclusionPath '{app}' -ErrorAction SilentlyContinue"""; \
    Flags: runhidden waituntilterminated

; アンインストール前に起動中プロセスを停止
Filename: "powershell.exe"; \
    Parameters: "-Command ""Get-Process python,pythonw -ErrorAction SilentlyContinue | Where-Object { $_.MainModule.FileName -like '{app}*' } | Stop-Process -Force"""; \
    Flags: runhidden

[Code]
// インストール開始前にポート8502を使っているプロセスを確認
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    // 既存プロセス停止（アップデート時の上書き対策）
    Exec('powershell.exe',
      '-Command "Stop-Process -Name pythonw -ErrorAction SilentlyContinue"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
