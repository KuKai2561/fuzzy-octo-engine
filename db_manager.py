# -*- coding: utf-8 -*-
import sqlite3, json, os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "proposals.db")


def _con():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row  # 列名でアクセス可能にする
    return con


def init_db():
    with _con() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT, project_name TEXT, company_name TEXT,
            prompt TEXT, tags TEXT, proposal_json TEXT)""")
        # 既存テーブルに列が不足している場合のマイグレーション
        cols = [r[1] for r in c.execute("PRAGMA table_info(proposals)").fetchall()]
        for col, typedef in [
            ("company_name",  "TEXT DEFAULT ''"),
            ("prompt",        "TEXT DEFAULT ''"),
            ("tags",          "TEXT DEFAULT '[]'"),
            ("proposal_json", "TEXT DEFAULT '{}'"),
        ]:
            if col not in cols:
                c.execute(f"ALTER TABLE proposals ADD COLUMN {col} {typedef}")
        c.commit()


def save(project_name, company_name, prompt, tags, proposal):
    with _con() as c:
        cur = c.execute(
            "INSERT INTO proposals(created_at,project_name,company_name,prompt,tags,proposal_json) VALUES(?,?,?,?,?,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M"), project_name, company_name,
             prompt, json.dumps(tags, ensure_ascii=False), json.dumps(proposal, ensure_ascii=False)))
        c.commit()
        return cur.lastrowid


def load_list():
    with _con() as c:
        rows = c.execute("SELECT id,created_at,project_name FROM proposals ORDER BY id DESC").fetchall()
    return [{"id": r["id"], "created_at": r["created_at"], "project_name": r["project_name"]} for r in rows]


def load_one(pid):
    with _con() as c:
        r = c.execute("SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()
    if not r:
        return {}
    return {
        "id":           r["id"],
        "created_at":   r["created_at"],
        "project_name": r["project_name"],
        "company_name": r["company_name"] or "",
        "prompt":       r["prompt"] or "",
        "tags":         json.loads(r["tags"] or "[]"),
        "proposal":     json.loads(r["proposal_json"] or "{}"),
    }


def delete(pid):
    with _con() as c:
        c.execute("DELETE FROM proposals WHERE id=?", (pid,))
        c.commit()


def get_company_names() -> list:
    """保存済み提案書から会社名の一覧（重複なし・最新順）を返す。"""
    try:
        with _con() as c:
            rows = c.execute(
                "SELECT DISTINCT company_name FROM proposals WHERE company_name != '' ORDER BY id DESC"
            ).fetchall()
        return [row[0].strip() for row in rows if row[0].strip()]
    except Exception:
        return []
