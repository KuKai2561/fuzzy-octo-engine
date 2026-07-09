@echo off
chcp 65001 > nul
echo ============================================================
echo  KuKai 技術提案書作成アプリ  インストーラービルド
echo  Python組み込み + Inno Setup でEXE作成
echo ============================================================
echo.

set APP_DIR=%~dp0
set BUILD_DIR=%APP_DIR%_build
set PYTHON_DIR=%BUILD_DIR%\python
set PYTHON_VER=3.11.9
set PYTHON_ZIP=python-3.11.9-embed-amd64.zip
set PYTHON_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip
set GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py

echo [手順1] ビルドフォルダ準備...
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
mkdir "%BUILD_DIR%"
mkdir "%PYTHON_DIR%"
echo   完了

echo.
echo [手順2] Python組み込みパッケージのダウンロード...
if not exist "%TEMP%\%PYTHON_ZIP%" (
    powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%TEMP%\%PYTHON_ZIP%'"
    echo   ダウンロード完了
) else (
    echo   キャッシュを使用: %TEMP%\%PYTHON_ZIP%
)
powershell -Command "Expand-Archive -Path '%TEMP%\%PYTHON_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force"
echo   展開完了: %PYTHON_DIR%

echo.
echo [手順3] pip を有効化...
powershell -Command "Invoke-WebRequest -Uri '%GET_PIP_URL%' -OutFile '%PYTHON_DIR%\get-pip.py'"

:: python311._pth を書き換えてsite-packagesを有効化
(
echo python311.zip
echo .
echo Lib\site-packages
echo.
echo import site
) > "%PYTHON_DIR%\python311._pth"

"%PYTHON_DIR%\python.exe" "%PYTHON_DIR%\get-pip.py" --no-warn-script-location
echo   pip 有効化完了

echo.
echo [手順4] 依存ライブラリをインストール...
"%PYTHON_DIR%\python.exe" -m pip install ^
    streamlit>=1.35.0 ^
    openpyxl>=3.1.0 ^
    python-docx>=1.1.0 ^
    anthropic>=0.25.0 ^
    pypdf>=4.0.0 ^
    --no-warn-script-location -q
echo   インストール完了

echo.
echo [手順5] アプリファイルをコピー...
copy /Y "%APP_DIR%KuKai_技術提案書作成.py"  "%BUILD_DIR%\KuKai_技術提案書作成.py"
copy /Y "%APP_DIR%claude_generator.py"       "%BUILD_DIR%\claude_generator.py"
copy /Y "%APP_DIR%generator.py"              "%BUILD_DIR%\generator.py"
copy /Y "%APP_DIR%key_manager.py"            "%BUILD_DIR%\key_manager.py"
copy /Y "%APP_DIR%reference_manager.py"      "%BUILD_DIR%\reference_manager.py"
copy /Y "%APP_DIR%excel_exporter.py"         "%BUILD_DIR%\excel_exporter.py"
copy /Y "%APP_DIR%db_manager.py"             "%BUILD_DIR%\db_manager.py"
copy /Y "%APP_DIR%launcher_silent.pyw"       "%BUILD_DIR%\launcher_silent.pyw"
echo   コピー完了

echo.
echo [手順6] Inno Setup コンパイル...
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
)
if not exist %ISCC% (
    echo   [エラー] Inno Setup 6 が見つかりません。
    echo   https://jrsoftware.org/isdl.php からインストールしてください。
    pause
    exit /b 1
)
%ISCC% "%APP_DIR%setup.iss"
echo   インストーラーEXE作成完了

echo.
echo ============================================================
echo  完了！ 生成物: %APP_DIR%Output\KuKai_技術提案書_Setup.exe
echo ============================================================
pause
