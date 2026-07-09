# 土木技術提案AIアプリ（技術提案書 様式４ 作成支援・スマホ／個人利用版）

三重県伊勢建設事務所向け・総合評価方式（簡易型B・対策なし型）の技術提案書（様式４）作成を支援するアプリです。
本フォルダは **販売用オリジナル版（`KuKai\技術提案書作成\`）とは別に、開発者本人が私用でスマホから使うために作成した個別コピー** です。

- ライセンス認証（MACアドレス紐付け等）は撤去済み。認証なしでそのまま起動できます。
- サーバー側PCのファイルシステムを直接操作する機能（エクスプローラーを開く等）は撤去し、
  すべて `st.download_button` によるブラウザ経由のダウンロードに統一しています。
- 留意点／理由のAI生成ロジック（2段階生成・文字数制限37字/45字充実等）、Excel/Word出力ロジック、
  過去提案書からの参照抽出ロジックは **オリジナル版と同一** です。Claude APIのモデルは
  `claude-opus-4-8`、`max_tokens=16000` を変更していません。

---

## 1. ローカルでの起動方法

このフォルダで以下を実行するだけです（オリジナル版と同じ）。

```bash
cd "KuKai\土木技術提案AIアプリ"
pip install -r requirements.txt
python -m streamlit run KuKai_技術提案書作成.py --server.port 8503
```

- `--server.port 8503` はオリジナル版（8502等）と衝突しないためのポート指定です。空いていれば他の番号でも構いません。
- 起動後、表示されたURL（例: `http://localhost:8503`）にPCのブラウザでアクセスして動作確認できます。
- 同一Wi-Fi内のスマホから使いたい場合は `--server.address 0.0.0.0` を追加し、
  PCのローカルIP（例: `http://192.168.x.x:8503`）にスマホのブラウザからアクセスしてください。

### APIキーの設定（ローカル）

以下のどちらかで設定します（優先順位は後述）。

**方法A: `.streamlit/secrets.toml` を使う（推奨）**

1. 同梱の `.streamlit/secrets.toml.example` を `.streamlit/secrets.toml` にコピー
2. 中の `ANTHROPIC_API_KEY` を自分のAnthropic APIキーに書き換える
   （`secrets.toml` は `.gitignore` 対象なので誤ってコミットされません）

**方法B: アプリ画面から入力する**

初回起動時に表示される「⚙️ 初期設定」画面、またはサイドバーの「⚙️ 設定」からAPIキーを入力して保存できます。
この場合、キーはこのフォルダの `config.json` に **平文で** ローカル保存されます（`.gitignore` 対象）。

---

## 2. Streamlit Community Cloud へのデプロイ手順

個人のGitHubアカウントに**プライベートリポジトリ**を作り、Streamlit Community Cloudと連携する想定の手順です。

### 手順

1. **GitHubにプライベートリポジトリを作成**
   - GitHubで新規リポジトリを作成（例: `dobokugijutsuteian-ai`）。**Private** を選択。
   - `config.json` や `.streamlit/secrets.toml` が誤って含まれていないか確認（`.gitignore` 済みなので通常は問題なし）。

2. **このフォルダの中身をリポジトリにpush**
   ```bash
   cd "KuKai\土木技術提案AIアプリ"
   git init
   git add .
   git commit -m "初回コミット：土木技術提案AIアプリ"
   git branch -M main
   git remote add origin https://github.com/<自分のアカウント>/dobokugijutsuteian-ai.git
   git push -u origin main
   ```

3. **Streamlit Community Cloud にサインアップ／ログイン**
   - [https://share.streamlit.io](https://share.streamlit.io) にアクセスし、GitHubアカウントでログイン。
   - 初回はGitHubとの連携（OAuth認可）を求められるので許可する。
   - プライベートリポジトリを使う場合、Streamlit Cloud側にそのリポジトリへのアクセス権限を追加で許可する必要があります
     （連携設定画面の「Configure」からリポジトリアクセスを個別に許可）。

4. **新しいアプリを作成（New app）**
   - Repository: 上記で作成したプライベートリポジトリを選択
   - Branch: `main`
   - Main file path: `KuKai_技術提案書作成.py`
   - App URL（任意）: 例 `dobokugijutsuteian-ai`
   - 「Deploy」をクリック

5. **Secrets（APIキー）を設定**
   - デプロイ後、アプリ管理画面の右上メニュー →「Settings」→「Secrets」を開く
   - 以下を貼り付けて保存する
     ```toml
     ANTHROPIC_API_KEY = "sk-ant-api03-ここに自分のAPIキー"
     ```
   - 保存すると自動的にアプリが再起動し、`st.secrets["ANTHROPIC_API_KEY"]` としてアプリから読み込まれます。

6. **動作確認**
   - 発行されたURL（例: `https://<your-app>.streamlit.app`）にスマホのブラウザでアクセス。
   - ブラウザタブに「土木技術提案AIアプリ」と表示され、サイドバーに
     「🔒 st.secrets から読み込み済み」と表示されればAPIキー設定は成功です。

### 更新方法

ローカルでコードを修正して `git push` するだけで、Streamlit Community Cloud側が自動的に再デプロイします。

---

## 3. APIキー読み込みの優先順位

`api_key_manager.py` が以下の順で読み込みます（ライセンス認証・MACアドレス紐付けは一切行いません）。

1. `st.secrets["ANTHROPIC_API_KEY"]`（Streamlit Cloud の Secrets、またはローカルの `.streamlit/secrets.toml`）
2. 環境変数 `ANTHROPIC_API_KEY`
3. `config.json`（ローカル動作用の平文保存。`.gitignore` 対象でリポジトリには含まれません）

`st.secrets` から読み込めている間は、アプリ画面からの「APIキーを変更」欄は表示されません
（Secretsの値が常に優先され、画面から変更しても反映されないため）。

---

## 4. データ永続化に関する重要な制約（Streamlit Community Cloud）

**Streamlit Community Cloud はコンテナが再起動するとファイルシステムの内容がリセットされます。**

このアプリは以下のデータをローカルファイルとして保存しています。

- `data/proposals.db`（SQLite：提案書の保存履歴）
- `data/prompt_history.json`（過去プロンプト履歴）
- `data/item_history.json`（評価項目の入力履歴）
- `data/references/`（過去の提出済み提案書＝参照資料）
- `data/current_docs/`（今回の工事資料の一時アップロード）
- `data/*.xlsx` / `data/*.docx`（生成したExcel/Wordファイル本体）

Streamlit Community Cloud上でアプリがスリープ→再起動したり、再デプロイされたりすると、
**これらのデータは消える可能性があります**。生成したExcel/Wordファイルは必ずその場で
「⬇️ ダウンロード」ボタンからスマホ本体（またはPC）にダウンロードして保存してください。

継続的にデータを保持したい場合は、将来的に外部ストレージ（例: Google Drive連携、S3等）や
外部DB（例: Supabase等）への保存に切り替える対応が必要です（本版では未対応）。

ローカルPCで起動している分には、このフォルダの `data/` にそのままファイルが残り続けるため、
この制約は影響しません。

---

## 5. 変わっていない機能（オリジナル版と共通）

- 留意点／理由のAI生成（2段階生成：留意点を項目ごと個別生成→理由をまとめて生成）
- 文字数制限（留意点37字以内、理由45字に近づけて充実・30字以下不可）
- Excel（様式４テンプレート書き込み）・Word出力ロジック
- 過去提出済み提案書（PDF/Excel）からのナレッジ抽出・参照ロジック
- Claude APIモデル：`claude-opus-4-8`、`max_tokens=16000`

## 6. このフォルダで変更した点（オリジナル版との差分）

- アプリ名を「土木技術提案AIアプリ」に統一（フォルダ名・ブラウザタブ表示・画面下部の表記）
- ライセンス認証（`key_manager.py`・MACアドレス紐付け）を撤去し、`api_key_manager.py` に置き換え
- 「📁 保存場所を開く」ボタン（`subprocess` + `explorer` でサーバーPCのフォルダを開く機能）を削除し、
  `st.download_button` によるブラウザダウンロードのみに統一
- `st.set_page_config(layout=...)` を `"wide"` → `"centered"` に変更
- 極端に細い `st.columns([9, 1])` 等をスマホでも押しやすい比率・縦積みに調整
- APIキーの取得元を `st.secrets` 優先（→環境変数→`config.json`平文）に変更
- `.gitignore` を追加し、`config.json` / `secrets.toml` / 生成データがリポジトリに含まれないようにした
