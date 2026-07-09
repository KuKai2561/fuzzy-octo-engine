# -*- coding: utf-8 -*-
"""
技術提案書作成アプリ ランチャー
ダブルクリックまたはコマンドラインから実行してください。
"""
import subprocess
import sys
import os
import time
import webbrowser
import socket

PORT = 8502
APP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "KuKai_技術提案書作成.py")


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def main():
    print("=" * 50)
    print("  技術提案書作成アプリ 起動中...")
    print("=" * 50)

    if is_port_in_use(PORT):
        print(f"ポート {PORT} はすでに使用中です。")
        print(f"ブラウザで http://localhost:{PORT} を開きます。")
        webbrowser.open(f"http://localhost:{PORT}")
        input("\nEnterキーで終了します...")
        return

    cmd = [
        sys.executable, "-m", "streamlit", "run",
        APP_FILE,
        "--server.port", str(PORT),
        "--server.headless", "false",
        "--browser.gatherUsageStats", "false",
    ]

    print(f"\nアプリを起動します: {APP_FILE}")
    print(f"URL: http://localhost:{PORT}\n")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )

    # サーバーが起動するまで待機（最大30秒）
    started = False
    deadline = time.time() + 30
    while time.time() < deadline:
        if proc.poll() is not None:
            # プロセスが終了（エラー）
            print("ERROR: アプリが起動できませんでした。")
            out, _ = proc.communicate()
            print(out)
            input("\nEnterキーで終了します...")
            return

        if is_port_in_use(PORT):
            started = True
            break

        time.sleep(0.5)

    if started:
        time.sleep(1.5)  # 少し待ってからブラウザを開く
        print("ブラウザを開きます...")
        webbrowser.open(f"http://localhost:{PORT}")
        print("\n✅ アプリが起動しました")
        print(f"   ブラウザで http://localhost:{PORT} を確認してください")
        print("\n   このウィンドウを閉じるとアプリも終了します。")
        print("   終了するには Ctrl+C を押してください。\n")
    else:
        print("タイムアウト: サーバーが起動しませんでした。")

    # プロセスが終了するまで出力を流し続ける
    try:
        for line in proc.stdout:
            if line.strip():
                print(line.rstrip())
    except KeyboardInterrupt:
        print("\n停止中...")
        proc.terminate()

    proc.wait()
    print("アプリを終了しました。")
    input("Enterキーで閉じます...")


if __name__ == "__main__":
    main()
