# -*- coding: utf-8 -*-
"""
土木技術提案AIアプリ（技術提案書（様式４）作成支援アプリ　スマホ・個人利用版）
【ウィザード型 3ステップ】
  Step1: 工事情報・施工条件プロンプト入力
  Step2: 留意点の確認・編集
  Step3: 各留意点の理由を4案から選択
  Step4: プレビュー・Excel出力

※ 本版はライセンス認証・MACアドレス紐付けを行わない個人利用版です。
   APIキーは st.secrets → 環境変数 → config.json（ローカルのみ）の優先順位で読み込みます。
"""
import os, sys, json, hashlib
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import generator as gen
import db_manager as db
import excel_exporter as ex
import claude_generator as cg
import reference_manager as rm
import api_key_manager as akm

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_OUT_DIR = os.path.join(_APP_DIR, "data")
_VERSION_FILE = os.path.join(_APP_DIR, "VERSION")


def _load_app_version() -> str:
    """VERSIONファイルからアプリのバージョン文字列を読み込む。commit・pushのたびに更新する。"""
    try:
        with open(_VERSION_FILE, encoding="utf-8") as f:
            return f.read().strip() or "?"
    except Exception:
        return "?"


def _load_api_key_ui() -> str:
    """APIキーを返す。未設定時は空文字を返す。"""
    return akm.load_api_key() or ""


def _save_api_key_ui(key: str):
    """APIキーを config.json に平文保存する（ローカル利用のフォールバック用）。"""
    akm.save_api_key(key)


# ─────────────────────────────────────
# プロンプト履歴管理
# ─────────────────────────────────────
_PROMPT_HIST_FILE = os.path.join(_APP_DIR, "data", "prompt_history.json")
_ITEM_HIST_FILE   = os.path.join(_APP_DIR, "data", "item_history.json")

def _load_prompt_history() -> list:
    if not os.path.exists(_PROMPT_HIST_FILE):
        return []
    try:
        with open(_PROMPT_HIST_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _save_prompt_to_history(prompt: str, project_name: str = "", company_name: str = ""):
    os.makedirs(os.path.dirname(_PROMPT_HIST_FILE), exist_ok=True)
    history = _load_prompt_history()
    # 同一テキストは重複させず先頭に移動
    history = [h for h in history if h["text"].strip() != prompt.strip()]
    history.insert(0, {
        "text": prompt,
        "project_name": project_name,
        "company_name": company_name,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    with open(_PROMPT_HIST_FILE, "w", encoding="utf-8") as f:
        json.dump(history[:30], f, ensure_ascii=False, indent=2)


def _load_project_name_history() -> list:
    """プロンプト履歴から工事名の一覧（重複なし・最新順）を返す。"""
    history = _load_prompt_history()
    seen = set()
    result = []
    for h in history:
        pn = h.get("project_name", "").strip()
        if pn and pn not in seen:
            seen.add(pn)
            result.append(pn)
    return result


def _load_company_name_history() -> list:
    """DBとプロンプト履歴から会社名の一覧（重複なし・最新順）を返す。"""
    seen = set()
    result = []
    try:
        for cn_str in db.get_company_names():
            cn = cn_str.strip()
            if cn and cn not in seen:
                seen.add(cn)
                result.append(cn)
    except Exception:
        pass
    for h in _load_prompt_history():
        cn = h.get("company_name", "").strip()
        if cn and cn not in seen:
            seen.add(cn)
            result.append(cn)
    return result

def _load_item_history() -> dict:
    """項目ラベル履歴を {0: [...], 1: [...], 2: [...]} で返す。デフォルト値は常に含む。"""
    defaults = {str(i): [gen.DEFAULT_ITEMS[i]] for i in range(3)}
    if not os.path.exists(_ITEM_HIST_FILE):
        return defaults
    try:
        with open(_ITEM_HIST_FILE, encoding="utf-8") as f:
            data = json.load(f)
        for i in range(3):
            key = str(i)
            items = data.get(key, [])
            if gen.DEFAULT_ITEMS[i] not in items:
                items.append(gen.DEFAULT_ITEMS[i])
            data[key] = items
        return data
    except Exception:
        return defaults

def _save_item_label(index: int, label: str):
    """指定ポジションの項目ラベルを履歴の先頭に追加する。デフォルト値は末尾に保持。"""
    os.makedirs(os.path.dirname(_ITEM_HIST_FILE), exist_ok=True)
    hist = _load_item_history()
    key = str(index)
    items = hist.get(key, [gen.DEFAULT_ITEMS[index]])
    items = [x for x in items if x.strip() != label.strip()]
    items.insert(0, label)
    default = gen.DEFAULT_ITEMS[index]
    if default not in items:
        items.append(default)
    hist[key] = items[:30]
    with open(_ITEM_HIST_FILE, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

def _prompt_hist_label(h: dict) -> str:
    date = h.get("saved_at", "")[:10]
    pn   = h.get("project_name", "")
    text = h.get("text", "")
    preview = text[:40] + ("…" if len(text) > 40 else "")
    if pn:
        return f"[{date}]  {pn[:18]}　／　{preview}"
    return f"[{date}]  {preview}"

# ─────────────────────────────────────
# 今回の工事 資料管理
# ─────────────────────────────────────
_CURRENT_DOCS_DIR = os.path.join(_APP_DIR, "data", "current_docs")

def _list_current_docs() -> list:
    if not os.path.exists(_CURRENT_DOCS_DIR):
        return []
    files = []
    for fname in sorted(os.listdir(_CURRENT_DOCS_DIR)):
        fpath = os.path.join(_CURRENT_DOCS_DIR, fname)
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M")
            files.append({"name": fname, "path": fpath, "size": size, "mtime": mtime})
    return files

def _save_current_doc(name: str, data: bytes):
    os.makedirs(_CURRENT_DOCS_DIR, exist_ok=True)
    with open(os.path.join(_CURRENT_DOCS_DIR, name), "wb") as f:
        f.write(data)

def _on_doc_upload():
    n = st.session_state.get("_doc_up_n", 0)
    for uf in (st.session_state.get(f"doc_uploader_{n}") or []):
        _save_current_doc(uf.name, uf.read())
    st.session_state["_doc_up_n"] = n + 1

def _on_ref_upload():
    n = st.session_state.get("_ref_up_n", 0)
    for uf in (st.session_state.get(f"ref_uploader_{n}") or []):
        rm.add(uf.name, uf.read())
    st.session_state["_ref_up_n"] = n + 1

def _delete_current_doc(name: str):
    fpath = os.path.join(_CURRENT_DOCS_DIR, name)
    if os.path.exists(fpath):
        os.remove(fpath)

def _get_current_docs_context() -> str:
    """current_docs フォルダ内のPDF・Excelテキストを結合して返す。"""
    if not os.path.exists(_CURRENT_DOCS_DIR):
        return ""
    try:
        import pypdf
    except ImportError:
        return ""
    parts = []
    for fname in sorted(os.listdir(_CURRENT_DOCS_DIR)):
        fpath = os.path.join(_CURRENT_DOCS_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext == ".pdf":
            try:
                reader = pypdf.PdfReader(fpath)
                text_pages = []
                for page in reader.pages:
                    t = page.extract_text() or ""
                    if t.strip():
                        text_pages.append(t.strip())
                if text_pages:
                    parts.append(f"▼ {fname}\n" + "\n".join(text_pages))
            except Exception:
                pass
        elif ext in (".xlsx", ".xls"):
            try:
                text = rm.extract_text_from_path(fpath)
                if text.strip():
                    parts.append(f"▼ {fname}\n" + text.strip())
            except Exception:
                pass
        else:
            # DOCX・画像等は現状未対応のためスキップ
            continue
    return "\n\n".join(parts)

# ─────────────────────────────────────
# ページ設定
# ─────────────────────────────────────
st.set_page_config(
    page_title="土木技術提案AIアプリ",
    page_icon="🏗️",
    layout="centered",
    initial_sidebar_state="collapsed",
)
db.init_db()

# ─────────────────────────────────────
# CSS
# ─────────────────────────────────────
st.markdown("""
<style>
body { font-family: "Meiryo", "Yu Gothic", sans-serif; }
.step-title {
    font-size:1.5rem; font-weight:bold; color:#1a3a5c;
    border-bottom:3px solid #1a3a5c; padding-bottom:.4rem; margin-bottom:1rem;
}
.item-bar {
    background:#e8f0fe; border-left:5px solid #2c5f9e;
    padding:.4rem .8rem; font-weight:bold; font-size:1rem;
    margin-top:1rem; margin-bottom:.5rem; border-radius:0 4px 4px 0;
}
.note-label { color:#1a3a5c; font-weight:bold; font-size:.95rem; margin-top:.6rem; }
.reason-box {
    background:#f0f4fb; border:1px solid #ccd6f0;
    border-radius:6px; padding:.6rem .9rem; margin:.2rem 0;
    font-size:.9rem; line-height:1.6;
}
.reason-box:hover { background:#dce8ff; }
.char-ok   { color:#28a745; font-size:.82rem; }
.char-warn { color:#fd7e14; font-size:.82rem; }
.char-over { color:#dc3545; font-size:.82rem; }
.preview-row { background:#f8f9fa; border:1px solid #dee2e6;
    border-radius:6px; padding:.7rem 1rem; margin:.4rem 0; font-size:.88rem; line-height:1.8; }
.chui-box { background:#fff8e1; border-left:4px solid #ffc107;
    padding:.5rem .8rem; font-size:.83rem; margin:.5rem 0; border-radius:0 4px 4px 0; }
.progress-label { font-size:.9rem; color:#555; font-weight:bold; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────
# セッション初期化
# ─────────────────────────────────────
def _init():
    defaults = {
        "step": 1,
        "project_name": "",
        "company_name": "",
        "prompt": "",
        "tags": [],
        "templates": {},
        "notes": {},
        # all_reasons: {item: [ [r1,r2,r3,r4], [r1,r2,r3,r4], [r1,r2,r3,r4] ]}
        "all_reasons": {},
        "item_labels": list(gen.DEFAULT_ITEMS),
        "item_categories": list(gen.DEFAULT_ITEMS),
        "last_excel_path": None,
        "last_excel_error": None,
        "last_word_path": None,
        "last_word_error": None,
        "docs_context": "",
        "_notes_gen": 0,
        "ai_model": "claude-opus-4-8",
        "_proj_input_mode": True,
        "_comp_input_mode": True,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()

# セッション開始時に一度だけ「今回の工事」資料フォルダを自動クリアする
# （過去の提出済み提案書＝reference_manager 側のデータはここでは一切触らない）
if "_docs_auto_cleared" not in st.session_state:
    for _doc in _list_current_docs():
        _delete_current_doc(_doc["name"])
    st.session_state["_docs_auto_cleared"] = True

def _sidebar():
    with st.sidebar:
        st.markdown("### ⚙️ 設定")
        st.markdown("**Claude APIキー**")
        current_key = _load_api_key_ui()
        if akm.is_from_secrets():
            st.caption("🔒 st.secrets から読み込み済み（アプリからの変更はできません）")
        elif current_key:
            masked = current_key[:4] + "****" + current_key[-4:]
            st.caption(f"設定済み（config.json）: {masked}")
        else:
            st.warning("未設定")

        if not akm.is_from_secrets():
            new_key = st.text_input("APIキーを変更", type="password", key="_sidebar_api_key",
                                    placeholder="sk-ant-api03-...")
            if st.button("保存", key="_sidebar_save_key", use_container_width=True):
                if new_key.strip():
                    _save_api_key_ui(new_key.strip())
                    st.success("保存しました")
                    st.rerun()


def page_setup():
    st.subheader("⚙️ 初期設定｜Claude APIキーの登録")
    st.error("APIキーが設定されていません。使用を開始する前に登録が必要です。")
    st.markdown("""
**APIキーの取得方法：**
1. [https://console.anthropic.com](https://console.anthropic.com) にアクセス
2. アカウント登録 → 「API Keys」からキーを発行
3. 「sk-ant-api03-...」で始まるキーをコピー
4. 以下に貼り付けて「保存して開始」をクリック

※ Streamlit Community Cloud にデプロイする場合は、この画面を使わず
　 アプリの Secrets に `ANTHROPIC_API_KEY` を設定してください（README参照）。
　 ここで保存したキーはこの実行環境の config.json にのみ平文で保存されます。
    """)
    new_key = st.text_input("APIキー", type="password", placeholder="sk-ant-api03-...",
                             key="_setup_api_key")
    if st.button("保存して開始", type="primary"):
        k = new_key.strip()
        if not k.startswith("sk-ant-"):
            st.error("APIキーの形式が正しくありません。「sk-ant-」で始まるキーを入力してください。")
        else:
            _save_api_key_ui(k)
            st.success("APIキーを保存しました。")
            st.rerun()

# ─────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────
_ITEM_EMOJIS = ["🗓️", "🦺", "🌊"]
NOTE_LABELS = ["①", "②", "③"]

def item_icon(i):
    labels = st.session_state.item_labels
    label = labels[i] if i < len(labels) else f"項目{i+1}"
    emoji = _ITEM_EMOJIS[i] if i < len(_ITEM_EMOJIS) else "📋"
    return f"{emoji} 項目{i+1}　{label}"

def go(step):
    st.session_state.step = step
    st.rerun()

def _render_chui():
    st.markdown('<div class="chui-box"><b>【様式４ 注意事項】</b><br>' +
                "<br>".join(f"・{c}" for c in gen.CHUI_JIKO) + "</div>",
                unsafe_allow_html=True)

def _progress_bar(current: int):
    labels = ["①情報入力", "②留意点確認", "③理由選択", "④出力"]
    cols = st.columns(4)
    for i, (col, label) in enumerate(zip(cols, labels)):
        with col:
            if i + 1 < current:
                st.success(f"✅ {label}", icon=None)
            elif i + 1 == current:
                st.info(f"▶ {label}", icon=None)
            else:
                st.markdown(f"<div style='color:#aaa;font-size:.85rem;'>　　{label}</div>",
                            unsafe_allow_html=True)

# ─────────────────────────────────────
# STEP 1 : 情報・プロンプト入力
# ─────────────────────────────────────
def page_step1():
    st.subheader("🏗️ STEP 1｜工事情報・施工条件の入力")
    _render_chui()

    col1, col2 = st.columns(2)
    with col1:
        # ── 工事名（セレクトボックス ↔ テキスト入力の切り替え）
        _proj_names = _load_project_name_history()
        _proj_default = st.session_state.project_name
        if _proj_names and not st.session_state.get("_proj_input_mode", False):
            _NEW_PROJ = "── 新しい工事名を入力 ──"
            _proj_sel_opts = _proj_names + [_NEW_PROJ]
            _proj_idx = _proj_sel_opts.index(_proj_default) if _proj_default in _proj_names else 0
            proj_sel = st.selectbox("工事名 ＊", options=_proj_sel_opts, index=_proj_idx, key="_proj_sel")
            if proj_sel == _NEW_PROJ:
                st.session_state["_proj_input_mode"] = True
                st.rerun()
            pn = proj_sel
        else:
            _p1, _p2 = st.columns([5, 1])
            with _p1:
                pn = st.text_input("工事名 ＊", value="" if _proj_default in _proj_names else _proj_default, key="pn_new")
            with _p2:
                if _proj_names:
                    st.write("")
                    if st.button("↩", key="_proj_back", help="過去の工事名から選択"):
                        st.session_state["_proj_input_mode"] = False
                        st.rerun()

        # ── 会社名（セレクトボックス ↔ テキスト入力の切り替え）
        _comp_names = _load_company_name_history()
        _comp_default = st.session_state.company_name
        if _comp_names and not st.session_state.get("_comp_input_mode", False):
            _NEW_COMP = "── 新しい会社名を入力 ──"
            _comp_sel_opts = _comp_names + [_NEW_COMP]
            _comp_idx = _comp_sel_opts.index(_comp_default) if _comp_default in _comp_names else 0
            comp_sel = st.selectbox("会社名 ＊", options=_comp_sel_opts, index=_comp_idx, key="_comp_sel")
            if comp_sel == _NEW_COMP:
                st.session_state["_comp_input_mode"] = True
                st.rerun()
            cn = comp_sel
        else:
            _c1, _c2 = st.columns([5, 1])
            with _c1:
                cn = st.text_input("会社名 ＊", value="" if _comp_default in _comp_names else _comp_default, key="cn_input")
            with _c2:
                if _comp_names:
                    st.write("")
                    if st.button("↩", key="_comp_back", help="過去の会社名から選択"):
                        st.session_state["_comp_input_mode"] = False
                        st.rerun()
    with col2:
        st.markdown("#### 📋 評価項目（３項目）の設定")
        st.caption("プルダウンで過去の項目を選択、またはテキストボックスに直接入力してください。")
        _item_hist = _load_item_history()
        new_item_labels = []
        for i in range(3):
            # プルダウン選択 → テキスト入力への pending 反映
            _pk = f"_pending_item_{i}"
            if _pk in st.session_state:
                st.session_state[f"item_label_{i}"] = st.session_state.pop(_pk)

            # 履歴オプション（選択肢: "─ 選択 ─" + 保存済みラベル一覧）
            _hist_opts = _item_hist.get(str(i), [gen.DEFAULT_ITEMS[i]])
            _sel_opts  = ["─ 過去の項目から選択 ─"] + _hist_opts

            def _make_item_handler(idx, opts):
                def _handler():
                    sel = st.session_state.get(f"item_sel_{idx}", 0)
                    if 0 < sel < len(opts):
                        st.session_state[f"_pending_item_{idx}"] = opts[sel]
                return _handler

            st.selectbox(
                f"項目{i+1}（履歴）",
                options=range(len(_sel_opts)),
                format_func=lambda j, opts=_sel_opts: opts[j],
                key=f"item_sel_{i}",
                on_change=_make_item_handler(i, _sel_opts),
                label_visibility="collapsed",
            )
            v = st.text_input(
                f"項目{i+1}",
                value="",
                key=f"item_label_{i}",
                placeholder=gen.DEFAULT_ITEMS[i],
                label_visibility="collapsed",
            )
            new_item_labels.append(v.strip() or gen.DEFAULT_ITEMS[i])

    st.markdown("---")
    _col_prompt_hd, _col_auto_btn = st.columns([5, 3])
    with _col_prompt_hd:
        st.markdown("#### 📝 施工条件プロンプト")
    with _col_auto_btn:
        st.write("")
        if st.button("🤖 工事資料から自動生成", key="_auto_prompt_btn", use_container_width=True):
            _auto_docs = _get_current_docs_context()
            if not _auto_docs:
                st.warning("先に工事資料をアップロードしてください。")
            else:
                with st.spinner("工事資料を解析し、類似事例・地域特性をWeb検索しながらプロンプトを生成中…（1分程度かかる場合があります）"):
                    try:
                        _auto_result = cg.generate_prompt_from_docs(
                            _auto_docs, pn or st.session_state.get("project_name", ""),
                            model=st.session_state["ai_model"],
                        )
                        st.session_state["prompt_textarea"] = _auto_result
                    except Exception as _e:
                        st.error(f"自動生成に失敗しました：{_e}")
    st.caption("現場の特徴・施工方法・周辺環境などを自由に記入してください。過去に使ったプロンプトはプルダウンから選択できます。")

    # ── 過去プロンプトのプルダウン
    _ph = _load_prompt_history()
    if _ph:
        def _on_prompt_select():
            idx = st.session_state.get("_prompt_hist_sel", 0)
            if idx > 0 and idx <= len(_ph):
                st.session_state["_pending_prompt"] = _ph[idx - 1]["text"]

        _opt_labels = ["─ 過去のプロンプトから選択する ─"] + [_prompt_hist_label(h) for h in _ph]
        st.selectbox(
            "過去プロンプト選択",
            options=range(len(_opt_labels)),
            format_func=lambda i: _opt_labels[i],
            key="_prompt_hist_sel",
            on_change=_on_prompt_select,
            label_visibility="collapsed",
        )

    # pending（プルダウン選択）をテキストエリアに適用
    if "_pending_prompt" in st.session_state:
        st.session_state["prompt_textarea"] = st.session_state.pop("_pending_prompt")

    _example_ph = ("例）主要工種・使用機械・作業内容・数量を記載。近接する道路・住宅・河川等の周辺状況、"
                   "施工時期の制限、騒音・振動・濁水等の対策要否、搬入経路や関係機関との調整事項があれば記載。")
    prompt = st.text_area(
        "施工条件プロンプト",
        key="prompt_textarea",
        height=140,
        placeholder=_example_ph,
        label_visibility="collapsed",
    )

    if prompt:
        tags = gen.parse_prompt(prompt)
        # プロンプト変更をセッションに即時反映（API呼び出しが常に最新値を参照するよう保証）
        st.session_state.prompt = prompt
        st.session_state.tags = tags
        if tags:
            st.markdown(f"**検出された条件タグ：** {' ／ '.join(tags)}")

    # ── 今回の工事 資料
    st.markdown("---")
    st.markdown("#### 📁 工事 資料（図面・仕様書・特記仕様書・位置図 等）")
    st.caption("工事に関する資料をアップロードしてください。複数ファイルを一度に選択できます。")

    _doc_n = st.session_state.get("_doc_up_n", 0)
    st.file_uploader(
        "資料アップロード",
        type=["pdf", "png", "jpg", "jpeg", "xlsx", "xls", "docx", "doc"],
        key=f"doc_uploader_{_doc_n}",
        label_visibility="collapsed",
        accept_multiple_files=True,
        on_change=_on_doc_upload,
    )

    _docs = _list_current_docs()
    if _docs:
        for _doc in _docs:
            _size_kb = _doc["size"] / 1024
            _size_str = f"{_size_kb:.0f} KB" if _size_kb < 1024 else f"{_size_kb/1024:.1f} MB"
            _ext = os.path.splitext(_doc["name"])[1].lower()
            _icon = "🖼️" if _ext in (".png", ".jpg", ".jpeg") else "📄"
            _col_doc, _col_del = st.columns([4, 1])
            with _col_doc:
                st.markdown(
                    f"{_icon} **{_doc['name']}**　"
                    f"<span style='color:#888;font-size:.82rem;'>{_doc['mtime']}　{_size_str}</span>",
                    unsafe_allow_html=True,
                )
            with _col_del:
                if st.button("削除", key=f"doc_del_{_doc['name']}", use_container_width=True):
                    _delete_current_doc(_doc["name"])
                    st.rerun()
    else:
        st.caption("まだ資料は登録されていません")

    # ── 過去の提出済み提案書（参照）
    st.markdown("---")
    st.markdown("#### 📚 過去の提出済み提案書（参照）")
    st.caption("登録した提案書をAI生成時の参照に使用します。PDF・Excelをアップロードしてください。")

    _ref_n = st.session_state.get("_ref_up_n", 0)
    st.file_uploader(
        "PDF / Excel をアップロード",
        type=["pdf", "xlsx", "xls"],
        key=f"ref_uploader_{_ref_n}",
        label_visibility="collapsed",
        accept_multiple_files=True,
        on_change=_on_ref_upload,
    )

    refs = rm.list_all()
    if refs:
        for ref in reversed(refs):
            ca = ref.get("chars", {})
            col_ref, col_del = st.columns([4, 1])
            with col_ref:
                st.markdown(f"📄 **{ref['filename']}**　"
                            f"<span style='color:#888;font-size:.82rem;'>{ref['added_at']}　"
                            f"留意点≈{ca.get('chui_avg','-')}字 / 理由≈{ca.get('riyu_avg','-')}字</span>",
                            unsafe_allow_html=True)
            with col_del:
                if st.button("削除", key=f"ref_del_{ref['id']}", use_container_width=True):
                    rm.delete(ref["id"])
                    st.rerun()
    else:
        st.caption("まだ登録された参照提案書はありません")

    st.markdown("---")
    if st.button("▶ 留意点を生成する", type="primary", use_container_width=True):
        if not pn.strip():
            st.warning("工事名を入力してください。")
            return
        if not cn.strip():
            st.warning("会社名を入力してください。")
            return
        if not prompt.strip():
            st.warning("施工条件プロンプトを入力してください。")
            return

        tags = gen.parse_prompt(prompt)
        st.session_state.project_name = pn
        st.session_state.company_name = cn
        st.session_state.prompt = prompt
        st.session_state.tags = tags
        st.session_state.item_labels = new_item_labels

        # プロンプトを履歴に保存
        _save_prompt_to_history(prompt, pn, cn)
        # 項目ラベルを履歴に保存
        for _i, _lbl in enumerate(new_item_labels):
            _save_item_label(_i, _lbl)

        templates = {}
        notes = {}
        all_reasons = {}
        item_categories = []

        # ── Claude AI 2段階生成
        notes_ok = False
        reasons_ok = False
        ref_ctx = rm.get_context()
        ref_count = len(rm.list_all())
        docs_ctx = _get_current_docs_context()
        st.session_state.docs_context = docs_ctx
        docs_count = len(_list_current_docs())

        # Step1: 留意点を項目ごとに個別生成
        try:
            _step1_ph = st.empty()
            for _i, _lbl in enumerate(new_item_labels):
                _step1_ph.info(
                    f"留意点を生成中… 項目{_i+1}/3「{_lbl}」"
                    + (f"　（工事資料{docs_count}件・過去提案書{ref_count}件参照）" if (docs_ctx or ref_ctx) else "")
                )
                _single = cg._generate_notes_single(
                    target_label=_lbl,
                    all_item_labels=new_item_labels,
                    construction_prompt=prompt,
                    reference_context=ref_ctx,
                    project_name=pn,
                    docs_context=docs_ctx,
                    model=st.session_state["ai_model"],
                )
                notes[_lbl] = _single
                tpls, cat = gen.select_templates_for_item(_lbl, tags, 3, index=_i)
                templates[_lbl] = tpls
                item_categories.append(cat)
            _step1_ph.empty()
            notes_ok = True
        except Exception as e:
            st.warning(f"留意点のAI生成に失敗しました。テンプレートを使用します。（{e}）")

        # Step2: 理由を生成（留意点生成が成功した場合のみ）
        if notes_ok:
            try:
                with st.spinner("Claude AIで各留意点に対する理由を生成中…"):
                    reasons_result = cg.generate_all_reasons(
                        new_item_labels, notes, prompt,
                        reference_context=ref_ctx,
                        project_name=pn,
                        docs_context=docs_ctx,
                        model=st.session_state["ai_model"],
                    )
                for label in new_item_labels:
                    all_reasons[label] = reasons_result.get(
                        label, [["", "", "", ""], ["", "", "", ""], ["", "", "", ""]]
                    )
                reasons_ok = True
            except Exception as e:
                st.warning(f"理由のAI生成に失敗しました。テンプレートを使用します。（{e}）")

        # ── テンプレートから選択（留意点AIエラー時のみ上書き）
        if not notes_ok:
            item_categories = []
            for i, label in enumerate(new_item_labels):
                tpls, cat = gen.select_templates_for_item(label, tags, 3, index=i)
                templates[label] = tpls
                notes[label] = [t["留意点"] for t in tpls]
                item_categories.append(cat)

        # 理由のフォールバック（理由AIエラー時のみ）
        if not reasons_ok:
            for i, label in enumerate(new_item_labels):
                tpls = templates.get(label) or gen.select_templates_for_item(label, tags, 3, index=i)[0]
                all_reasons[label] = [
                    [c["text"] for c in tpl.get("理由候補", [{"text": ""}] * 4)]
                    for tpl in tpls
                ]

        st.session_state.templates = templates
        st.session_state.notes = notes
        st.session_state.all_reasons = all_reasons
        st.session_state.item_categories = item_categories
        st.session_state._notes_gen = st.session_state.get("_notes_gen", 0) + 1
        go(2)



# ─────────────────────────────────────
# STEP 2 : 留意点の確認・編集
# ─────────────────────────────────────
def page_step2():
    st.subheader("✏️ STEP 2｜留意点の確認・編集")

    items = st.session_state.item_labels
    notes_ver = st.session_state.get("_notes_gen", 0)

    for i, item in enumerate(items):
        emoji = _ITEM_EMOJIS[i] if i < len(_ITEM_EMOJIS) else "📋"
        st.markdown(f"#### {emoji} 評価項目 {i+1}　{item}")
        cur_notes = st.session_state.notes.get(item, ["", "", ""])

        for ni in range(3):
            wkey = f"s2n_{notes_ver}_{i}_{ni}"
            val = cur_notes[ni] if ni < len(cur_notes) else ""

            st.markdown(f"**留意点{NOTE_LABELS[ni]}**")
            col_edit, col_pick = st.columns([6, 4])

            with col_edit:
                new_val = st.text_area(
                    f"留意点{NOTE_LABELS[ni]}",
                    value=val,
                    height=90,
                    key=wkey,
                    label_visibility="collapsed",
                    placeholder="〜に留意する。",
                )
                ns = st.session_state.notes.setdefault(item, ["", "", ""])
                while len(ns) < 3:
                    ns.append("")
                ns[ni] = new_val

            with col_pick:
                st.caption("別の候補に差し替え")
                _cand_key = f"_cands_{notes_ver}_{i}_{ni}"
                ai_cands = st.session_state.get(_cand_key)

                if st.button("🤖 AIで候補を生成", key=f"gai_{notes_ver}_{i}_{ni}",
                             use_container_width=True):
                    try:
                        existing = st.session_state.notes.get(item, [])
                        ref_ctx = rm.get_context()
                        with st.spinner(f"「{item}」の代替候補をAIで生成中…"):
                            new_cands = cg.generate_alternative_notes(
                                item, list(items),
                                st.session_state.get("prompt", ""),
                                existing_notes=[n for n in existing if n and n.strip()],
                                reference_context=ref_ctx,
                                project_name=st.session_state.get("project_name", ""),
                                docs_context=st.session_state.get("docs_context", ""),
                                model=st.session_state["ai_model"],
                            )
                        st.session_state[_cand_key] = new_cands
                        st.rerun()
                    except Exception as e:
                        st.warning(f"候補の生成に失敗しました: {e}")

                if not ai_cands:
                    st.caption("「🤖 AIで候補を生成」をクリックしてください")
                else:
                    disp_labels = [f"{t['留意点'][:38]}…" for t in ai_cands]
                    sel = st.selectbox(
                        "候補",
                        options=range(len(ai_cands)),
                        format_func=lambda idx, lb=disp_labels: lb[idx],
                        key=f"pick_{notes_ver}_{i}_{ni}",
                        label_visibility="collapsed",
                    )
                    if st.button("この候補を使う", key=f"use_{notes_ver}_{i}_{ni}"):
                        if sel is not None and sel < len(ai_cands):
                            new_note = ai_cands[sel]["留意点"]
                            ns2 = st.session_state.notes.setdefault(item, ["", "", ""])
                            while len(ns2) < 3:
                                ns2.append("")
                            ns2[ni] = new_note
                            dummy_tpl = {"留意点": new_note, "tags": [], "理由候補": []}
                            tpls2 = st.session_state.templates.setdefault(item, [])
                            while len(tpls2) <= ni:
                                tpls2.append(dummy_tpl)
                            tpls2[ni] = dummy_tpl
                            try:
                                ref_ctx = rm.get_context()
                                with st.spinner("選択した留意点の理由をAIで生成中…"):
                                    new_reasons = cg.generate_reasons(
                                        new_note, item, list(items),
                                        st.session_state.get("prompt", ""),
                                        ref_ctx,
                                        project_name=st.session_state.get("project_name", ""),
                                        docs_context=st.session_state.get("docs_context", ""),
                                        model=st.session_state["ai_model"],
                                    )
                                ar = st.session_state.all_reasons.setdefault(item, [])
                                while len(ar) < 3:
                                    ar.append(["", "", "", ""])
                                ar[ni] = new_reasons
                            except Exception as e:
                                st.warning(f"理由の生成に失敗しました: {e}")
                            st.session_state._notes_gen = notes_ver + 1
                            st.rerun()

        st.markdown("---")

    st.markdown("---")
    col_back, col_next = st.columns(2)
    col_back.button("◀ 戻る", on_click=go, args=(1,), use_container_width=True)
    if col_next.button("▶ 理由を選ぶ", type="primary", use_container_width=True):
        all_ok = True
        for item in st.session_state.item_labels:
            for ni in range(3):
                ns = st.session_state.notes.get(item, [])
                if ni >= len(ns) or not ns[ni].strip():
                    all_ok = False
        if not all_ok:
            st.warning("空白の留意点があります。全て入力してから次へ進んでください。")
        else:
            go(3)


# ─────────────────────────────────────
# STEP 3 : 理由の確認・編集（留意点1つにつき理由4つ）
# ─────────────────────────────────────
REASON_LABELS = ["①", "②", "③", "④"]

def page_step3():
    st.subheader("✍️ STEP 3｜理由の確認・編集（各留意点につき理由４つ）")
    st.caption("各留意点に対して４つの理由が自動生成されています。内容を確認・編集してください。４つの理由がそれぞれExcelテンプレートの1行に書き込まれます。")

    tabs = st.tabs([item_icon(i) for i in range(3)])
    notes_ver = st.session_state.get("_notes_gen", 0)

    for i, (tab, item) in enumerate(zip(tabs, st.session_state.item_labels)):
        with tab:
            tpls = st.session_state.templates.get(item, [])
            notes_list = st.session_state.notes.get(item, ["", "", ""])

            # all_reasons[item] = [[r1,r2,r3,r4], [r1,r2,r3,r4], [r1,r2,r3,r4]]
            cur_all = st.session_state.all_reasons.get(item, [])

            for ni in range(3):
                note_text = notes_list[ni] if ni < len(notes_list) else ""
                tpl = tpls[ni] if ni < len(tpls) else {}
                candidates = tpl.get("理由候補", [])

                # 現在の4つの理由（存在しなければ候補テキストで初期化）
                if ni < len(cur_all):
                    cur_reasons = list(cur_all[ni])
                else:
                    cur_reasons = [c["text"] for c in candidates] if candidates else ["", "", "", ""]
                while len(cur_reasons) < 4:
                    cur_reasons.append("")

                st.markdown(f"**留意点{NOTE_LABELS[ni]}**")
                st.info(f"【留意点】　{note_text}")

                st.markdown("**▼ 理由①〜④（Excelに1行ずつ書き込まれます）**")

                new_reasons = []
                for ri in range(4):
                    label = candidates[ri]["label"] if ri < len(candidates) else f"理由{REASON_LABELS[ri]}"
                    val = cur_reasons[ri]
                    new_val = st.text_area(
                        f"理由{REASON_LABELS[ri]}　{label}",
                        value=val,
                        height=68,
                        key=f"reason_{notes_ver}_{i}_{ni}_{ri}",
                        placeholder="理由を入力してください（〜ため。で終わると自然です）",
                    )
                    n_chars = len(new_val)
                    if n_chars > 65:
                        st.caption(f"{n_chars}文字 ⚠️長い")
                    else:
                        st.caption(f"{n_chars}文字")
                    new_reasons.append(new_val)

                # 更新をセッション状態に保存
                while len(st.session_state.all_reasons.setdefault(item, [])) <= ni:
                    st.session_state.all_reasons[item].append(["", "", "", ""])
                st.session_state.all_reasons[item][ni] = new_reasons

                st.divider()

    st.markdown("---")
    col_back, col_next = st.columns(2)
    col_back.button("◀ 戻る", on_click=go, args=(2,), use_container_width=True)
    if col_next.button("▶ プレビュー・出力へ", type="primary", use_container_width=True):
        missing = []
        for i, item in enumerate(st.session_state.item_labels):
            for ni in range(3):
                reasons = st.session_state.all_reasons.get(item, [])
                r4 = reasons[ni] if ni < len(reasons) else []
                if not any(r.strip() for r in r4):
                    missing.append(f"{item_icon(i)} 留意点{NOTE_LABELS[ni]}")
        if missing:
            st.warning("以下の理由が未入力です:\n" + "\n".join(missing))
        else:
            go(4)


# ─────────────────────────────────────
# STEP 4 : プレビュー・出力
# ─────────────────────────────────────
def page_step4():
    st.subheader("👁️ STEP 4｜プレビュー・Excel出力")

    # proposal データ構造を作成
    proposal = {}
    for item in st.session_state.item_labels:
        ns = st.session_state.notes.get(item, ["", "", ""])
        ar = st.session_state.all_reasons.get(item, [])
        entries = []
        for ni in range(3):
            r4 = ar[ni] if ni < len(ar) else ["", "", "", ""]
            while len(r4) < 4:
                r4.append("")
            entries.append({
                "留意点": ns[ni] if ni < len(ns) else "",
                "理由リスト": list(r4),
            })
        proposal[item] = entries

    # ── AI予想採点（50点満点）
    st.markdown("### 🎯 AI予想採点（50点満点）")
    st.caption(
        "世界最高水準の技術提案書審査AIが、確定した留意点・理由一式を厳格・公正に採点します。"
        "APIを利用するため、ボタンを押した時のみ実行されます。"
    )

    all_notes_for_eval = {
        item: [proposal[item][ni]["留意点"] for ni in range(3)]
        for item in st.session_state.item_labels
    }
    all_reasons_for_eval = {
        item: [proposal[item][ni]["理由リスト"] for ni in range(3)]
        for item in st.session_state.item_labels
    }
    _score_sig = hashlib.sha256(json.dumps(
        {
            "notes": all_notes_for_eval,
            "reasons": all_reasons_for_eval,
            "prompt": st.session_state.get("prompt", ""),
            "project_name": st.session_state.project_name,
        },
        ensure_ascii=False, sort_keys=True,
    ).encode("utf-8")).hexdigest()

    _has_score = bool(st.session_state.get("ai_score_result"))
    _score_btn_label = "🔄 再採点する" if _has_score else "🎯 予想点数の算出"
    if st.button(_score_btn_label, type="primary", key="run_ai_score"):
        try:
            ref_ctx = rm.get_context()
            with st.spinner("AIが提案書を厳格に採点中…"):
                score_result = cg.evaluate_proposal_score(
                    st.session_state.item_labels,
                    all_notes_for_eval,
                    all_reasons_for_eval,
                    st.session_state.get("prompt", ""),
                    project_name=st.session_state.project_name,
                    docs_context=st.session_state.get("docs_context", ""),
                    reference_context=ref_ctx,
                    model=st.session_state["ai_model"],
                )
            st.session_state["ai_score_result"] = score_result
            st.session_state["ai_score_signature"] = _score_sig
            st.session_state["ai_score_error"] = None
        except Exception as e:
            st.session_state["ai_score_error"] = f"採点に失敗しました: {e}"

    if st.session_state.get("ai_score_error"):
        st.warning(st.session_state["ai_score_error"])

    _score_result = st.session_state.get("ai_score_result")
    if _score_result:
        if st.session_state.get("ai_score_signature") != _score_sig:
            st.info(
                "⚠️ 留意点・理由がこの採点結果の取得後に変更されています。"
                "以下は古い内容に基づく点数です。「🔄 再採点する」を押して最新の内容で更新してください。"
            )

        total = _score_result.get("total_score", 0)
        max_score = _score_result.get("max_score", 50) or 50

        col_metric, col_bar = st.columns([2, 6])
        with col_metric:
            st.metric("予想点数", f"{total} / {max_score} 点")
        with col_bar:
            st.markdown("<br>", unsafe_allow_html=True)
            st.progress(min(max(total / max_score, 0.0), 1.0))

        # ── 世界最強の技術提案エージェントによるご指導
        _guidance = (_score_result.get("guidance_message") or "").strip()
        if _guidance:
            st.markdown("#### 🎓 指導")
            st.info(_guidance)

        st.markdown("#### 📊 項目別内訳")
        for s in _score_result.get("item_scores", []):
            st.markdown(f"**{s.get('item', '')}**：{s.get('score', 0)} / {s.get('max', 15)} 点")
            if s.get("comment"):
                st.caption(s["comment"])

        _overall = _score_result.get("overall") or {}
        if _overall:
            st.markdown(f"**全体の一貫性・完成度**：{_overall.get('score', 0)} / {_overall.get('max', 5)} 点")
            if _overall.get("comment"):
                st.caption(_overall["comment"])

        # ── 具体的な修正指示
        st.markdown("#### ✍️ 具体的な修正指示")
        _revisions = _score_result.get("revision_instructions", [])
        if _revisions:
            for rv in _revisions:
                _heading = "　".join(x for x in [rv.get("item", ""), rv.get("target", "")] if x)
                st.markdown(f"**{_heading}**" if _heading else "**修正指示**")
                if rv.get("current_text"):
                    st.markdown(f"- 現状：~~{rv['current_text']}~~")
                if rv.get("suggested_text"):
                    st.markdown(f"- 修正案：**{rv['suggested_text']}**")
                if rv.get("reason"):
                    st.caption(rv["reason"])
                st.divider()
        else:
            st.caption("大きな減点要因は見つかりませんでした。")

        col_str, col_imp = st.columns(2)
        with col_str:
            st.markdown("#### ✅ 優れている点")
            _strengths = _score_result.get("strengths", [])
            if _strengths:
                for s in _strengths:
                    st.markdown(f"- {s}")
            else:
                st.caption("特になし")
        with col_imp:
            st.markdown("#### 🛠️ 改善すべき点")
            _improvements = _score_result.get("improvements", [])
            if _improvements:
                for s in _improvements:
                    st.markdown(f"- {s}")
            else:
                st.caption("特になし")
    else:
        st.caption("まだ採点されていません。「🎯 予想点数の算出」を押してください。")

    st.markdown("---")

    # ── プレビュー表示
    st.markdown(f"""
    <div class="preview-row">
    <b>（様式４）　技術提案に関する技術資料</b><br>
    工事名：{st.session_state.project_name}<br>
    会社名：{st.session_state.company_name}
    </div>
    """, unsafe_allow_html=True)

    for item_no, item in enumerate(st.session_state.item_labels, 1):
        st.markdown(f"#### 項目{item_no}　{item}")
        for ni in range(3):
            note   = proposal[item][ni]["留意点"]
            r_list = proposal[item][ni]["理由リスト"]
            reason_rows = "".join(
                f'<div style="display:flex;gap:8px;padding:2px 0;">'
                f'<span style="min-width:52px;width:52px;color:#555;white-space:nowrap;font-size:.85rem;">理由{REASON_LABELS[ri]}</span>'
                f'<span style="color:#333;line-height:1.6;">{r}</span>'
                f'</div>'
                for ri, r in enumerate(r_list) if r.strip()
            )
            st.markdown(f"""
            <div class="preview-row">
              <div style="display:flex;gap:8px;padding-bottom:5px;border-bottom:1px solid #dee2e6;margin-bottom:3px;">
                <span style="min-width:52px;width:52px;font-weight:bold;white-space:nowrap;color:#1a3a5c;">留意点{NOTE_LABELS[ni]}</span>
                <span style="font-weight:bold;line-height:1.6;">{note}</span>
              </div>
              {reason_rows}
            </div>
            """, unsafe_allow_html=True)
        st.markdown("")

    # ── 出力エリア（スマホでの見やすさを優先し、Excel/Wordを横並びではなく縦に並べる）
    st.markdown("---")

    with st.container():
        st.markdown("#### 📥 Excel出力（様式４テンプレートに書き込み）")
        out_dir = st.text_input(
            "保存先フォルダ",
            value=_DEFAULT_OUT_DIR,
            key="out_excel",
        )
        if st.button("Excelに出力する", type="primary", use_container_width=True):
            with st.spinner("Excelを生成中..."):
                try:
                    path = ex.export(
                        st.session_state.project_name,
                        st.session_state.company_name,
                        proposal, out_dir
                    )
                    st.session_state["last_excel_path"] = path
                    st.session_state["last_excel_error"] = None
                except PermissionError:
                    st.session_state["last_excel_error"] = (
                        "アクセス拒否エラー: テンプレートファイルが Excel で開かれている可能性があります。"
                        "\n「評価項目一覧・様式.xlsx」を閉じてから再度お試しください。"
                    )
                    st.session_state["last_excel_path"] = None
                except FileNotFoundError as e:
                    st.session_state["last_excel_error"] = f"ファイルが見つかりません: {e}"
                    st.session_state["last_excel_path"] = None
                except Exception as e:
                    import traceback, logging
                    logging.error(traceback.format_exc())
                    st.session_state["last_excel_error"] = f"Excel生成中にエラーが発生しました。\n詳細: {type(e).__name__}: {e}"
                    st.session_state["last_excel_path"] = None

        # 結果表示（ボタンを押した後も維持）
        if st.session_state.get("last_excel_error"):
            st.error(st.session_state["last_excel_error"])
        elif st.session_state.get("last_excel_path"):
            p = st.session_state["last_excel_path"]
            st.success(f"✅ 生成しました。下のボタンからダウンロードしてください。")
            try:
                with open(p, "rb") as f:
                    st.download_button(
                        "⬇️ ダウンロード", f.read(),
                        file_name=os.path.basename(p),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
            except FileNotFoundError:
                st.warning("ファイルが見つかりません。再度出力してください。")
                st.session_state.pop("last_excel_path", None)

    st.markdown("---")
    with st.container():
        st.markdown("#### 📄 Word出力（A4文書として生成）")
        out_dir_w = st.text_input(
            "保存先フォルダ（Word）",
            value=_DEFAULT_OUT_DIR,
            key="out_word",
        )
        if st.button("Wordに出力する", use_container_width=True):
            with st.spinner("Wordを生成中..."):
                try:
                    path = ex.export_word(
                        st.session_state.project_name,
                        st.session_state.company_name,
                        proposal, out_dir_w
                    )
                    st.session_state["last_word_path"] = path
                    st.session_state["last_word_error"] = None
                except ImportError:
                    st.session_state["last_word_error"] = "Word出力に必要なコンポーネントが見つかりません。アプリを再インストールしてください。"
                    st.session_state["last_word_path"] = None
                except Exception as e:
                    import traceback, logging
                    logging.error(traceback.format_exc())
                    st.session_state["last_word_error"] = f"Word生成中にエラーが発生しました。\n詳細: {type(e).__name__}: {e}"
                    st.session_state["last_word_path"] = None

        if st.session_state.get("last_word_error"):
            st.error(st.session_state["last_word_error"])
        elif st.session_state.get("last_word_path"):
            p = st.session_state["last_word_path"]
            st.success(f"✅ 生成しました。下のボタンからダウンロードしてください。")
            try:
                with open(p, "rb") as f:
                    st.download_button(
                        "⬇️ ダウンロード（Word）", f.read(),
                        file_name=os.path.basename(p),
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )
            except FileNotFoundError:
                st.warning("ファイルが見つかりません。再度出力してください。")
                st.session_state.pop("last_word_path", None)

    st.markdown("---")
    # スマホでの押しやすさを優先し、3ボタンを横並びではなく縦に並べる
    if st.button("💾 この提案を履歴に保存", use_container_width=True):
        pid = db.save(
            st.session_state.project_name,
            st.session_state.company_name,
            st.session_state.prompt,
            st.session_state.tags,
            proposal,
        )
        st.success(f"✅ 保存しました（ID: {pid}）")

    st.button("◀ 理由選択に戻る", on_click=go, args=(3,), use_container_width=True)

    if st.button("🔄 最初からやり直す", use_container_width=True):
        for k in ["step", "project_name", "company_name", "prompt", "tags",
                  "templates", "notes", "all_reasons",
                  "item_labels", "item_categories", "docs_context", "_notes_gen",
                  "last_excel_path", "last_excel_error", "last_word_path", "last_word_error",
                  "_comp_input_mode", "_proj_input_mode",
                  "ai_score_result", "ai_score_signature", "ai_score_error"]:
            if k in st.session_state:
                del st.session_state[k]
        # notes_ver が次回0から再スタートするため、versioned なウィジェットキー
        # （s2n_/reason_/_cands_/gai_/pick_/use_ 等）を残すと前回の値が再利用されて
        # しまう。該当キーを一括で削除する。
        _stale_prefixes = ("s2n_", "reason_", "_cands_", "gai_", "pick_", "use_")
        for k in list(st.session_state.keys()):
            if k.startswith(_stale_prefixes):
                del st.session_state[k]
        go(1)


# ─────────────────────────────────────
# メインルーティング
# ─────────────────────────────────────
_sidebar()
step = st.session_state.step

st.caption(f"🔧 v{_load_app_version()}")

if not _load_api_key_ui():
    page_setup()
else:
    # AIモデル切り替え（デフォルト: Opus 4.8）
    _MODEL_LABELS = {"claude-opus-4-8": "🟢 Opus 4.8", "claude-fable-5": "🟣 Fable 5"}
    _model_options = list(_MODEL_LABELS.keys())
    _current_model = st.session_state.get("ai_model", "claude-opus-4-8")
    if _current_model not in _model_options:
        _current_model = "claude-opus-4-8"
    _selected_model = st.radio(
        "AIモデル",
        options=_model_options,
        format_func=lambda m: _MODEL_LABELS[m],
        index=_model_options.index(_current_model),
        horizontal=True,
        key="_ai_model_radio",
        label_visibility="collapsed",
    )
    st.session_state["ai_model"] = _selected_model

    _progress_bar(step)
    st.write("")

    if step == 1:
        page_step1()
    elif step == 2:
        page_step2()
    elif step == 3:
        page_step3()
    elif step == 4:
        page_step4()

st.markdown("---")
st.caption("土木技術提案AIアプリ ｜ KuKai")
