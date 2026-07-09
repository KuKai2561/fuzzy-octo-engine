@echo off
chcp 65001 > nul
echo ============================================================
echo  KuKai 技術提案書作成アプリ  [開発モード起動]
echo ============================================================
set KUKAI_DEV_MODE=1
python -m streamlit run KuKai_技術提案書作成.py --server.port 8502
pause
