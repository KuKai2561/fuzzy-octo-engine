# -*- coding: utf-8 -*-
"""
インストール版サイレントランチャー
- コンソールウィンドウなしでStreamlitを起動
- ブラウザを開いて終了（Streamlitはバックグラウンド継続）
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
PYTHON  = os.path.join(BASE_DIR, "python", "python.exe")

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

    if is_port_in_use(PORT):
        kill_port(PORT)
        for _ in range(20):
            time.sleep(0.3)
            if not is_port_in_use(PORT):
                break

    if is_port_in_use(PORT):
        webbrowser.open(f"http://localhost:{PORT}")
        return

    subprocess.Popen(
        [PYTHON, "-m", "streamlit", "run", APP_FILE,
         "--server.port", str(PORT),
         "--server.headless", "true",
         "--browser.gatherUsageStats", "false"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=BASE_DIR,
        creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
    )

    deadline = time.time() + 30
    while time.time() < deadline:
        if is_port_in_use(PORT):
            break
        time.sleep(0.5)

    time.sleep(1)
    webbrowser.open(f"http://localhost:{PORT}")


if __name__ == "__main__":
    main()
