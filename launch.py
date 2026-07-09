# -*- coding: utf-8 -*-
"""
起動スクリプト
- Streamlit を独立プロセスとして起動
- ポート8502 が上がったらブラウザを開いて終了
"""
import subprocess
import sys
import os
import time
import webbrowser
import socket

PORT = 8502
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_FILE = os.path.join(BASE_DIR, "KuKai_技術提案書作成.py")

# Windows専用: デタッチドプロセスとして起動（親が終了しても継続）
DETACHED_PROCESS = 0x00000008
CREATE_NO_WINDOW = 0x08000000


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def kill_port(port):
    try:
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    subprocess.run(["taskkill", "/F", "/PID", parts[-1]],
                                   capture_output=True, timeout=5)
    except Exception:
        pass


def main():
    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    print("=" * 50)
    print("  技術提案書作成アプリ 起動中...")
    print("=" * 50)

    # 旧プロセスをクリア
    if is_port_in_use(PORT):
        print(f"ポート {PORT} を使用中のプロセスを停止します...")
        kill_port(PORT)
        for _ in range(10):
            time.sleep(0.5)
            if not is_port_in_use(PORT):
                break

    if is_port_in_use(PORT):
        print(f"アプリはすでに起動中です。ブラウザを開きます...")
        webbrowser.open(f"http://localhost:{PORT}")
        input("\nEnterキーで終了します...")
        return

    print(f"\nStreamlit を起動します...")

    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", APP_FILE,
             "--server.port", str(PORT),
             "--server.headless", "true",
             "--browser.gatherUsageStats", "false"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=BASE_DIR,
            # デタッチドプロセス: このウィンドウを閉じてもアプリは継続
            creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
        )
    except Exception as e:
        print(f"\n起動エラー: {e}")
        input("Enterキーで終了します...")
        return

    print(f"サーバー起動待機中 (PID:{proc.pid})", end="", flush=True)

    started = False
    deadline = time.time() + 30
    while time.time() < deadline:
        if is_port_in_use(PORT):
            started = True
            break
        time.sleep(0.5)
        print(".", end="", flush=True)

    if not started:
        print("\nタイムアウト: 30秒以内にサーバーが起動しませんでした。")
        proc.terminate()
        input("Enterキーで終了します...")
        return

    time.sleep(1)
    print(f"\n\n  アプリが起動しました！")
    print(f"  URL: http://localhost:{PORT}")
    print("\n  ブラウザを開きます...")
    print("\n  アプリを終了するには:")
    print("  タスクマネージャーで python を終了してください。\n")

    webbrowser.open(f"http://localhost:{PORT}")

    input("Enterキーでこのウィンドウを閉じます（アプリは継続します）...")


if __name__ == "__main__":
    main()
