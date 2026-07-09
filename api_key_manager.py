# -*- coding: utf-8 -*-
"""
APIキー管理モジュール（スマホ・個人利用版）

ライセンス認証やMACアドレス紐付けは行わない。取得優先順位は以下の通り：
  1. st.secrets["ANTHROPIC_API_KEY"]
     - Streamlit Community Cloud の Secrets、またはローカルの
       .streamlit/secrets.toml に設定した値
  2. 環境変数 ANTHROPIC_API_KEY
  3. config.json（ローカル動作用の平文保存。.gitignore 対象でリポジトリには含めない）

st.secrets から読み込めた場合はそれを最優先し、アプリ内の「APIキーを保存」操作は
config.json への平文保存（フォールバック用）としてのみ機能する。
"""
import os
import json

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_APP_DIR, "config.json")


def _from_secrets() -> str:
    """st.secrets からAPIキーを取得する。未設定・取得不可の場合は空文字を返す。"""
    try:
        import streamlit as st
        val = st.secrets.get("ANTHROPIC_API_KEY", "")
        return (val or "").strip()
    except Exception:
        # st.secrets 未設定（secrets.toml が無い等）でも例外にせず空文字を返す
        return ""


def _read_config() -> dict:
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _write_config(cfg: dict):
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def is_from_secrets() -> bool:
    """現在有効なAPIキーが st.secrets 由来かどうかを返す。"""
    return bool(_from_secrets())


def load_api_key() -> str:
    """
    APIキーを取得する。
    優先順位: st.secrets → 環境変数 ANTHROPIC_API_KEY → config.json（平文）
    見つからない場合は空文字を返す。
    """
    key = _from_secrets()
    if key:
        return key

    env_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if env_key:
        return env_key

    cfg = _read_config()
    return (cfg.get("anthropic_api_key") or "").strip()


def save_api_key(api_key: str):
    """
    APIキーを config.json に平文保存する（ローカル利用のフォールバック用）。
    st.secrets 経由で運用している場合、この関数で保存した値は
    st.secrets が優先されるため実質的に使われない。
    """
    cfg = _read_config()
    cfg["anthropic_api_key"] = api_key.strip()
    _write_config(cfg)
