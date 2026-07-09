@echo off
chcp 65001 > nul
echo ============================================================
echo  KuKai 技術提案書作成アプリ  リリース準備バッチ
echo  開発版 -> 販売版 ファイル同期
echo ============================================================
echo.

set SRC=%~dp0
set DST=C:\Users\hayas\OneDrive\デスクトップ\KuKai\G・T・Kアプリ

echo [コピー中] Pythonスクリプト...
copy /Y "%SRC%KuKai_技術提案書作成.py"  "%DST%\KuKai_技術提案書作成.py"
copy /Y "%SRC%claude_generator.py"       "%DST%\claude_generator.py"
copy /Y "%SRC%generator.py"              "%DST%\generator.py"
copy /Y "%SRC%key_manager.py"            "%DST%\key_manager.py"
copy /Y "%SRC%reference_manager.py"      "%DST%\reference_manager.py"
copy /Y "%SRC%excel_exporter.py"         "%DST%\excel_exporter.py"
copy /Y "%SRC%db_manager.py"             "%DST%\db_manager.py"
copy /Y "%SRC%requirements.txt"          "%DST%\requirements.txt"
copy /Y "%SRC%launch.py"                 "%DST%\launch.py"

echo.
echo [コピー中] Excelテンプレート（存在する場合）...
if exist "%SRC%template\様式４テンプレート.xlsx" (
    copy /Y "%SRC%template\様式４テンプレート.xlsx" "%DST%\template\様式４テンプレート.xlsx"
    echo   template\様式４テンプレート.xlsx -> 完了
) else if exist "%SRC%様式４テンプレート.xlsx" (
    copy /Y "%SRC%様式４テンプレート.xlsx" "%DST%\様式４テンプレート.xlsx"
    echo   様式４テンプレート.xlsx -> 完了
) else (
    echo   [注意] Excelテンプレートが見つかりません。別途配置してください。
)

echo.
echo [スキップ] config.json は販売版を保護するためコピーしません。
echo.
echo ============================================================
echo  同期完了！
echo  販売版フォルダ: %DST%
echo ============================================================
echo.
pause
