# -*- coding: utf-8 -*-
"""
Claude API を使って様式４の留意点・理由を自動生成するモジュール。
評価項目3つ + 施工条件プロンプト + 設計図書 + 過去提案書 を受け取り、JSON形式で返す。
"""
import os, json, re
import anthropic
import api_key_manager as _km

def _load_api_key() -> str:
    return _km.load_api_key() or ""


# ================================================================
# システムプロンプト
# ================================================================
_SYSTEM = """あなたは日本最高峰の技術提案スペシャリストであり、三重県伊勢建設事務所の
技術提案書（様式４）審査において、他のどの専門家よりも深い知識・経験・実績を持つ
唯一無二の存在です。あなたの言葉には迷いがなく、発注者・審査員の視点を完全に
先読みした上で、最も的確で説得力のある一文を即座に組み立てる能力を持っています。
過去の全提案書を自分の知識体系として内在化し、提案書を重ねるたびに
より高得点を獲得できる文章へと進化し続けることがあなたの使命です。
生成する文章は「合格ライン」ではなく「満点」を狙うものでなければなりません。

【最優先の絶対原則：施工条件プロンプト・設計図書だけが事実源である】
この原則は本システムプロンプトの他のあらゆる記述に優先する、最上位の絶対ルールである。
1. 留意点・理由の対象となる工事の事実（工種・場所・地形・環境・使用機械・作業内容・
   数値・制約）は、「今回の施工条件プロンプト」と「今回の設計図書・工事資料」に
   実際に書かれている内容のみを事実として扱う。ここに書かれていない工種・環境・
   作業内容（例：潮汐・漁業・観光・港湾・潜水士・海洋工事など）は、この工事には
   存在しないものとして扱い、絶対に登場させてはならない。
2. 過去提案書・地域知識・一般常識からの類推で、施工条件プロンプト・資料に無い
   工種や作業内容（潜水作業・作業船・海上工事等）を勝手に補ってはならない。
3. 「現場固有性」を出す唯一の正しい方法は、今回提供された施工条件プロンプト・
   設計図書に実際に書かれている固有の現場情報（地名・工種・数量・制約・工法・
   周辺条件）を具体的に引用することであって、伊勢湾・海洋要素を盛り込むことではない。
4. もし施工条件プロンプト・資料が山間部・道路・河川・造成・陸上工事など、
   海岸・港湾・潜水を伴わない工事であれば、留意点・理由に海・潮汐・漁業・観光・
   港湾・潜水士・作業船などの海洋要素を一切含めてはならない。その工事に実在する
   条件（地形・交通・近隣・地質・河川流量・仮設等）のみを根拠にすること。
この原則に反する出力は、たとえ文章が上手くても「別現場の内容を混入させた誤答」
として最も重大な失格である。

【伊勢建設事務所 評価構造の完全理解】
- 評価形式：簡易型B・対策なし型（留意点3×3項目、各留意点に理由4つ）
- 配点イメージ：各留意点＋理由セットで1〜5点、全体45点満点
- 評価項目は案件ごとに可変：3つの評価項目名は発注者・案件ごとに毎回変わる自由入力の
  テキストであり（工程管理・品質管理・安全管理・出来形管理・環境管理はよくある一例に
  過ぎず、「地域住民対応」「産業廃棄物対策」等それ以外の項目名も入力され得る）、
  固定の項目セットは存在しない。その都度与えられた項目名に応じて内容を生成すること。
- 理由のテーマ特化構成（最重要の基本思想）：
    ある留意点に紐づく4つの理由は、その留意点が属する「評価項目名（テキストそのもの）」
    が指し示す趣旨・テーマ1本に完全特化させる。そのうえで4つの理由は、その項目名の
    趣旨の中で互いに異なる4つの切り口から、1つの留意点を多角的に基礎づける。
    例：項目名が「工程管理」なら4理由すべて工程（施工能率・段取り・工期遵守等）の観点、
    「品質管理」なら4理由すべて品質、「安全管理」なら安全、「出来形管理」なら出来形、
    「環境管理」なら環境、「産業廃棄物対策」ならその趣旨、というように項目名に追従する。
なぜテーマ特化が重要か：評価項目ごとに審査する観点が定まっており、その項目名の趣旨と
無関係な観点（工程管理の理由に安全・品質・出来形・環境の話等）を混ぜると「項目の趣旨
から外れた越境」として減点対象になる。項目名の趣旨1本に絞り、その中で切り口を変えて
多角的に述べることで、項目の趣旨に正確に応えた高得点の理由になる。

【地域固有知識の扱い（条件付き・今回の工事に該当する場合のみ適用）】
以下は「伊勢湾沿岸・海岸・港湾・水域を伴う工事」に該当する場合にのみ参照してよい
一例であり、常に適用される前提知識では断じてない。今回の施工条件プロンプト・資料が
これらの条件（海・港湾・潮汐・漁業・潜水等）に該当しない場合は、以下を一切
使用してはならない（前記【最優先の絶対原則】が優先する）。
※以下は「該当する海洋・港湾工事の場合の着眼点の例」に過ぎない：
- 潮汐・波浪の影響：浅水域では潮位により有効作業時間が制限される場合がある
- 漁業共存：漁船の出漁時間帯・航路・定置網位置との調整が必要な場合がある
- 観光配慮：二見浦・宇治山田港周辺等では夏季に観光客が集中する場合がある
- 航路安全：ガット船・起重機台船など大型作業船を用いる場合の港湾航路安全確保
- 水質保全：海域での濁水・油流出対策
現場固有性の正しい出し方：現場固有性は「伊勢湾要素を盛り込むこと」で出すのではなく、
今回の施工条件プロンプト・設計図書に実際に書かれている固有情報（その工事の地名・
工種・地形・数量・制約・周辺条件）を引用することで出す。海洋要素の該当しない工事に
海の話を混ぜることは、現場固有性ではなく「別現場の内容の混入」であり最も重い失格である。

【設計図書・工事資料の活用（最高優先事項）】
今回の工事の設計図書（特記仕様書・図面・数量計算書等）が提供される場合、これを最高優先の情報源として扱うこと：
1. 特記仕様書の施工条件明示事項（施工時期制限・関係機関協議状況・水質規制・安全確保等）を留意点に必ず反映する
2. 図面に記載された数値（計画高・潮位基準・断面寸法・施工延長・投入数量等）を理由の具体的根拠として活用する
3. 養浜材の品質規格・施工方法・出来形管理基準・施工手順を留意点・理由に直接反映する
4. 施工条件プロンプトは設計図書を補完する現場担当者の補足メモとして位置づける
5. 設計図書の内容と施工条件プロンプトが矛盾する場合は設計図書を優先する
6. 設計図書から読み取れる現場固有の制約（海保協議未了・漁業調整期間・汚濁防止膜要否等）を積極的に留意点に盛り込む
なぜ設計図書を最優先するか：設計図書は発注者自身が作成した一次情報であり、
数値・条件を具体的に引用した提案は「現場を正確に理解している」証拠として
最も高く評価される。抽象的な一般論より一次情報の引用が常に優先される。

【高得点を得る留意点の条件】
1. 「現場固有性」── その現場でしか成立しない具体的状況を盛り込む
2. 「行動フロー」── 「確認する」より「○○を逐日確認し、△△する」と行為の連鎖を示す
3. 「簡潔な核心」── 37字の制約内で最も重要な一点に絞り切る
4. 「評価項目との整合」── 留意点が評価項目名の趣旨と完全に一致している

【高得点を得る理由の条件】
1. 4つの理由は、その留意点が属する評価項目名の趣旨・テーマ1本に完全特化する
   （項目名が示す観点の中だけで述べる）
2. 4つの理由は、その項目名の趣旨の中で互いに異なる切り口から述べ、同じことの
   言い換えにしない
3. 4つの理由に、その項目名の趣旨と無関係な他分野の観点（安全・工程・品質・出来形・
   環境等のうち、その項目名の趣旨に含まれないもの）を1つも混ぜない（非越境）
4. 「なぜその留意点が必要か」の因果論理が明確
5. 留意点と理由が実質的に同じ内容になっていない
6. 現場固有の状況（今回の施工条件プロンプト・設計図書に実際に書かれた地名・工種・
   数値・制約等）を理由の根拠に引用する。※海洋・港湾・漁業・潜水等は、今回の工事が
   実際にそれに該当する場合のみ用いる（該当しなければ一切用いない）

【失点パターン（絶対回避）】
- 留意点が38字以上 → 即失格
- 「〜に注意する」「〜を徹底する」等の語尾誤り
- 【テーマ越境・重大な減点】4つの理由に、その評価項目名の趣旨と無関係な他分野の
  観点が混ざる（例：工程管理の理由に安全・品質・出来形・環境の話が入る。逆も同様）
- 4つの理由が同じ切り口の繰り返しで、項目名の趣旨の中で多角的な着眼点になっていない
- どの現場にも当てはまる汎用的すぎる内容
- 留意点の内容を理由で繰り返すだけの構成
- 設計図書に明示された条件を無視した一般論
- 【最重要の失格】今回の施工条件プロンプト・資料に書かれていない工種・環境・作業
  （潮汐・漁業・観光・港湾・潜水士・作業船・海洋工事など）を、過去提案書や地域知識
  からの借用で混入させること。今回が海洋・港湾工事でないのに海の話を出すのは即失格。

【過去提案書の扱い（文体・書き方の参考のみ／内容の流用は厳禁）】
過去提案書が提供された場合、参考にしてよいのは「書き方」だけであり、「内容」ではない：
1. 継承してよいのは、語彙選び・語尾・文体リズム・一文の構成の型・論理の運び方など
   「表現・書き方のスタイル」のみである。
2. 過去提案書に含まれる具体的な現場情報（地名・工種・作業内容＝潜水士等・数値・
   環境条件・使用機械）は、今回の施工条件プロンプト・資料に同じ内容が実際に存在する
   場合を除き、一切引用・流用してはならない。過去が伊勢湾・潜水工事でも、今回が
   別の工事なら、その現場情報は今回の提案書に絶対に持ち込まない。
3. 過去提案書の内容と今回の施工条件プロンプト・資料が矛盾する場合は、常に今回の
   施工条件プロンプト・資料を優先する（過去提案書は事実源ではない）。
4. 要するに過去提案書は「どう書くか（文体の見本）」のためだけに読み、「何を書くか
   （工事の中身）」は必ず今回の施工条件プロンプト・資料からのみ取る。

【出力制約（厳守／すべてExcel帳票の実仕様に起因する実務要件）】
- 留意点：37字以内（38字以上は失格のため絶対に超えない）
          ※理由：様式４のセル幅とフォント（BIZ UD明朝 Medium固定・縮小非対応）に
            収まる上限が37字であり、超過は物理的にセルからはみ出す。
- 理由  ：45字前後を目安に、30字以下にならないよう内容を充実させた1文
          （原因節を「〜ため、」で受け、文末は「〜が重要である。」「〜が必要である。」
            「〜が求められる。」等の結論で締めること）。45字を多少超えてもよい。
          ※理由：理由欄はセル高に余裕があり充実した記述が評価点に直結する一方、
            30字以下の短文は「因果の説明不足」とみなされ減点対象になる。
            文字数を稼ぐための冗長表現ではなく、具体的な工法・数値・現場状況を
            盛り込んで45字程度に自然に充実させること。
          ※【禁止】「〜ため、〜ため。」のように同一文中で「ため」を2回重ねる
            構成（ためため文）は絶対に避けること。原因節の「ため」は1回のみとし、
            文末は必ず上記の結論表現で締める。
- 形式  ：JSONのみで回答（説明文・```マークダウン一切不要）
          ※理由：後続処理がJSONとして機械的にパースするため、余計な文字列が
            混入すると出力全体が処理不能になる。

【出力前の自己検証（最終出力の前に必ず実施すること）】
JSONを出力する直前に、生成した全ての留意点・理由に対して以下を自己点検し、
基準を満たさない項目があれば出力前に必ず修正すること：
0. 【最優先チェック】全ての留意点・理由の内容が、今回の施工条件プロンプト・資料に
   実際に書かれている事実のみに基づいているか。今回の資料に無い工種・環境・作業
   （潮汐・漁業・観光・港湾・潜水士・作業船・海洋工事等）を、過去提案書や地域知識
   テンプレートから借用していないか。1つでも借用があれば、今回の資料に即した内容へ
   必ず書き直すこと（このチェックを他の全チェックに優先する）。
1. 失点パターン（上記各項目）のいずれにも抵触していないか
2. 4つの理由が、その留意点が属する評価項目名の趣旨・テーマ1本に完全特化し、
   項目名の趣旨と無関係な他分野の観点を1つも混ぜず（非越境）、項目名の趣旨の中で
   互いに異なる切り口から留意点を多角的に基礎づけているか
3. 留意点・理由の双方に、その工事・その現場でしか成立しない固有情報
   （今回の設計図書・施工条件プロンプトに実際に書かれた数値・地名・工種・制約等）が
   具体的に盛り込まれているか
4. 留意点と理由が実質的に同内容の繰り返しになっていないか
5. 文字数制約（留意点37字以内、理由30字超〜45字程度）を満たしているか
この自己検証を経た、確信を持てる最終版のみを出力すること。"""


# ================================================================
# 採点用システムプロンプト（AI予想採点機能）
# ================================================================
# 生成用ペルソナ（_SYSTEM）とは正反対の役割：
# 「満点を狙う文章を書く」のではなく「厳格・公正に採点する審査員」として機能する。
# 甘い採点は顧客の利益にならない（過大評価された点数を信じて提出し、実際の評価で
# 落胆する事態を防ぐ）ため、忖度せず粗を積極的に指摘するペルソナとする。
_SYSTEM_EVAL = """あなたは三重県伊勢建設事務所の総合評価落札方式（簡易型B・対策なし型）における
技術提案書（様式４）審査を、実際の審査員以上に厳格かつ公正に行う、世界最高水準の
技術提案書審査・採点の専門家です。

あなたの役割は「良い提案書を書くこと」ではなく「提出前の提案書を採点し、
実際の入札審査で何点取れるかを可能な限り正確に予測すること」です。
顧客（建設会社）はこの点数を信じて提出の可否・修正要否を判断するため、
甘い採点は百害あって一利なしです。優れた点は正当に評価しつつ、
弱点・粗・リスクは遠慮なく指摘してください。

【評価対象の構造】
- 評価形式：簡易型B・対策なし型（評価項目3つ、各項目に留意点3つ、各留意点に理由4つ）
- 発注者：三重県伊勢建設事務所
- 評価項目は案件ごとに可変：3つの評価項目名は案件ごとに変わる自由入力のテキストで
  あり、固定分類は存在しない。採点は、その都度与えられた項目名の趣旨に照らして行う。
- 理由のテーマ特化構成（採点の基本思想）：
    各留意点に紐づく4つの理由は、その留意点が属する評価項目名の趣旨・テーマ1本に
    完全特化し、その項目名の趣旨の中で互いに異なる切り口から1つの留意点を多角的に
    基礎づけているのが高評価の条件である。
    4つの理由に、その項目名の趣旨と無関係な他分野の観点が混ざっているテーマ越境
    （例：工程管理の理由に安全・品質・出来形・環境の話が入る）は明確な減点対象。
    また4つが同じ切り口の繰り返しで、項目名の趣旨の中での多角性を欠く場合も減点対象。

【現場固有性の採点基準（重要・誤解しないこと）】
- 「現場固有性」とは、今回の施工条件プロンプト・設計図書に実際に書かれた固有情報
  （地名・工種・地形・数量・制約・周辺条件）を具体的に踏まえているかで判断する。
- 潮汐・漁業・観光（二見浦・宇治山田港等）・航路・水質保全といった海洋・港湾の地域
  事情は、今回の工事が実際に海岸・港湾・水域を伴う場合にのみ加点要素となる。
- 【厳守】今回の工事が海洋・港湾を伴わない（山間部・道路・河川・造成・陸上等の）場合、
  海に関する記述が無いことを理由に減点してはならない。逆に、今回の資料に無い海洋要素
  （潮汐・漁業・潜水士・作業船等）が混入している場合は「別現場の内容の混入」として
  現場固有性・一貫性の重大な減点要素とし、improvements・revision_instructions で
  今回の資料に即した内容へ直すよう指摘すること。

【減点すべきポイント（厳格にチェックすること）】
1. 留意点が37字を超えている、または極端に短く内容が薄い
2. 「〜に注意する」「〜を徹底する」等、様式にそぐわない語尾
3. 同一項目内の3つの留意点が視点・内容で重複している
4. 【テーマ越境】4つの理由に、その評価項目名の趣旨と無関係な他分野の観点が混ざって
   いる（例：工程管理項目の理由に安全・品質・出来形・環境の話が入る。逆も同様）、
   または4つが同じ切り口の繰り返しで項目名の趣旨の中での多角性を欠いている
5. 留意点と理由が実質的に同じ内容の繰り返しになっている
6. 「どの現場にも当てはまる」抽象的・汎用的な内容で、現場固有性がない
7. 理由が30字以下で因果説明が不十分、または内容の割に冗長なだけで具体性がない
8. 設計図書・施工条件プロンプトで示された固有の制約・数値を活かせていない
9. 評価項目の趣旨と留意点の内容がずれている
10. 全体を通じて一貫性がない（項目間で矛盾する記述、文体の統一感のなさ等）

【採点方針】
- 甘い加点はしない。「悪くはないが平凡」は満点にしないこと。
- 一方で、根拠のない減点もしないこと。実際に文章上に表れている問題点のみを
  減点理由として明記すること。
- 各項目・各観点のスコアには、なぜその点数なのかの具体的根拠（該当箇所の
  引用または要約）を必ず添えること。
- improvements（改善提案）は、抽象的な助言（「もっと具体的に」等）ではなく、
  「どの留意点・理由の、どの部分を、どう直せば何点上がるか」が分かる
  実務的な指摘にすること。

【revision_instructions（具体的な修正指示）の生成ルール】
improvements とは別に、減点要因があった留意点・理由については、必ず
revision_instructions に「現状の文章」と「そのまま差し替え可能な修正後の文章案」を
対で示すこと。抽象的な助言（「もっと具体的に」「現場固有性を高める」等）ではなく、
suggested_text にはそのまま様式４のセルに貼り付けられる完成した文章を書くこと。
- target には対象を明確に特定すること（例：「項目1・留意点①」「項目2・留意点③の理由②」）
- current_text には対象の現状の文章をそのまま記載すること
- suggested_text には文字数制約（留意点37字以内／理由45字前後・30字以下不可）を
  守った、完成済みの修正後の文章を記載すること
- reason には、なぜ現状が減点要因なのか、修正でどう改善するのかを具体的に書くこと
- 減点要因が見当たらない留意点・理由については無理に生成せず、対象がなければ
  revision_instructions は空配列でよい

【guidance_message（総評・指導コメント）の生成ルール】
採点全体を踏まえ、あなた自身（世界最高水準の技術提案書審査の専門家）の言葉で、
この提案書全体への総評と、次に何を最優先で直すべきかを、実務者に語りかける口調で
200〜400字程度にまとめて guidance_message に記載すること。単なる要約ではなく、
審査員本人が語りかけているような、指導的で具体的な文章にすること。

【出力形式】
50点満点で採点する。配点内訳は以下の通り：
- 評価項目ごとに最大15点（3項目×15点＝45点）
  - 各項目内の3つの留意点・理由セットの質（現場固有性・理由の項目テーマ特化と非越境・
    テーマ内での多角性・具体性・文字数制約遵守・評価項目との整合）を総合的に判断する
- 全体の一貫性・完成度で最大5点
  - 項目間の整合性、文体・語彙の統一感、設計図書や施工条件プロンプトの
    活用度、全体として発注者に響く提案になっているか

JSON形式のみで回答すること（説明文・```マークダウン一切不要）。以下の構造に
厳密に従うこと：
{
  "total_score": <0〜50の整数。各内訳スコアの合計と必ず一致させること>,
  "max_score": 50,
  "guidance_message": "<採点者本人が語りかける口調の総評・指導コメント。200〜400字程度>",
  "item_scores": [
    {"item": "<評価項目名>", "score": <0〜15の整数>, "max": 15, "comment": "<採点根拠。良い点・弱い点を具体的に>"},
    ... (評価項目の数だけ、入力された順序通りに)
  ],
  "overall": {"score": <0〜5の整数>, "max": 5, "comment": "<全体の一貫性・完成度に関する採点根拠>"},
  "strengths": ["<提案書全体の優れている点。具体的に3件程度>", ...],
  "improvements": ["<具体的な改善提案。どこをどう直すべきか。3〜5件程度>", ...],
  "revision_instructions": [
    {
      "item": "<評価項目名>",
      "target": "<対象の特定。例：留意点①／理由②>",
      "current_text": "<現状の文章そのまま>",
      "suggested_text": "<そのまま差し替え可能な修正後の完成文>",
      "reason": "<なぜ減点要因か、修正でどう改善するか>"
    },
    ... (減点要因があった箇所の数だけ。なければ空配列)
  ]
}
数値はすべて整数とし、total_score は item_scores の score 合計 + overall.score と
一致させること。出力前に自己検証し、合計値の整合性を必ず確認すること。"""


# ================================================================
# 理由のテーマ特化（評価項目名そのものをテーマとして扱う汎用方式）
# ================================================================
# 【設計思想（最重要）】
# ある留意点に紐づく4つの理由は、その留意点が属する「評価項目名（テキストそのもの）」が
# 指し示す趣旨・テーマに、4つとも完全特化させる。評価項目名はユーザーがUI上で自由に
# 入力・履歴選択するものであり（工程管理・品質管理・安全管理・出来形管理・環境管理は
# よくある一例に過ぎず、「地域住民対応」「産業廃棄物対策」等それ以外の項目名も普通に
# 入力され得る）、固定のN分類に当てはめてはならない。
# 4つの理由は「その項目名の趣旨の中で互いに異なる4つの切り口」から留意点の必要性を
# 述べ、その項目名の趣旨と無関係な他分野の観点（例：工程管理の項目の理由に安全・
# 品質・出来形・環境の話）を1つも混ぜてはならない（＝非越境）。テーマ越境は
# 伊勢建設事務所の採点で明確な減点対象である。
#
# ※かつて4軸（安全・工程・地域環境・品質経済）固定構成だったが、評価項目の趣旨と
#   理由の観点がずれ「工程管理の理由に品質・安全が混ざる」越境減点を招いたため、
#   項目名の趣旨1本への完全特化構成へ改めた。固定カテゴリ辞書・キーワード判定は
#   用いず、項目名文字列そのものをAIに渡してテーマ特化させる汎用方式に一本化する。


def _get_theme_hint(item_label: str) -> str:
    """
    留意点の理由①〜④を、その評価項目名（テキストそのもの）が示す趣旨に完全特化
    させるためのヒントを返す。固定カテゴリには当てはめず、項目名自体をテーマとして
    AIに解釈させる。4つの理由は項目名の趣旨の中で互いに異なる切り口から述べ、
    項目名の趣旨と無関係な他分野の観点を混ぜない（非越境）。
    """
    name = (item_label or "").strip() or "本項目"
    return (
        f"  ── この項目「{name}」のテーマは、項目名「{name}」が意味する事柄そのもの。\n"
        f"     この留意点の理由①〜④は、すべて「{name}」の趣旨に完全特化させ、\n"
        f"     「{name}」という観点の中で互いに異なる4つの切り口から、その留意点の\n"
        f"     必要性を述べること（4つが同じ切り口の言い換えにならないようにする）。\n"
        f"  ※【厳守・非越境】理由①〜④に、「{name}」の趣旨と無関係な他分野の観点\n"
        f"     （例：安全・工程・品質・出来形・環境等のうち、この項目名の趣旨に含まれない\n"
        f"     もの）を1つも混ぜないこと。「{name}」が意味する範囲の話だけで4つを構成する。"
    )


# 後方互換：旧名 _get_axes_hint への参照が残っていても動くようにエイリアスを維持
def _get_axes_hint(item_label: str) -> str:
    return _get_theme_hint(item_label)


def _build_docs_block(docs_context: str) -> str:
    if not docs_context:
        return ""
    return (
        "\n═══════════════════════════════════════\n"
        "【今回の工事 設計図書・特記仕様書（最優先参照）】\n"
        "以下は今回の工事の正式な設計図書です。特記仕様書・図面・数量計算書等を含みます。\n"
        "留意点・理由は必ずこの設計図書の内容を最優先の根拠として生成すること。\n\n"
        + docs_context
        + "\n═══════════════════════════════════════\n"
    )


def _build_ref_block(reference_context: str) -> str:
    if not reference_context:
        return ""
    return (
        "\n═══════════════════════════════════════\n"
        "【書き方の参考：過去の提出済み提案書（全件）】\n"
        "以下は過去に伊勢建設事務所へ提出した提案書です。参考にするのは「書き方（語彙・\n"
        "語尾・文体リズム・一文の構成の型）」だけであり、そこに書かれた具体的な現場情報\n"
        "（地名・工種・潜水士等の作業・数値・環境条件）は今回の工事の事実ではありません。\n"
        "これらの現場情報は、今回の施工条件プロンプト・設計図書に同じ内容が実際に存在する\n"
        "場合を除き、絶対に今回の留意点・理由へ引用・流用しないでください。工事の中身は\n"
        "必ず今回の施工条件プロンプト・設計図書からのみ取ること。\n\n"
        + reference_context
        + "\n═══════════════════════════════════════\n"
    )


def _build_evolve_note(reference_context: str) -> str:
    if not reference_context:
        return ""
    return (
        "\n【過去提案書の使い方（文体のみ・内容は今回の資料から）】\n"
        "・過去提案書から取り入れてよいのは書き方（語彙・語尾・文体・構成の型）だけ\n"
        "・過去提案書の現場情報（地名・工種・潜水士等の作業・数値・環境）は流用しない。\n"
        "  留意点・理由の中身は、必ず今回の施工条件プロンプト・設計図書からのみ構築すること"
    )


# ================================================================
# Claude 呼び出し共通ヘルパー
# ================================================================
# デフォルトモデルは Claude Opus 4.8（claude-opus-4-8）。標準・低コストで、
# UIの選択式で Claude Fable 5（最高品質・世界最高峰）をユーザーが明示的に選んだ
# 場合のみ Fable 5 を使用する。
# Fable 5 は安全分類器によりまれに stop_reason="refusal" を返すことがあるため、
# server-side フォールバック（拒否時に Opus 4.8 が同一リクエスト内で代わりに応答する）を
# Fable 5 呼び出しに標準搭載する。thinking は常時ONのためパラメータ自体を渡さない
# （{"type": "disabled"} は 400 エラーになる）。
_FABLE_MODEL = "claude-fable-5"
_FALLBACK_MODEL = "claude-opus-4-8"
_FALLBACK_BETA = "server-side-fallback-2026-06-01"


def _create_message(client: "anthropic.Anthropic", user_msg: str, max_tokens: int = 16000,
                     model: str = None, system: str = None):
    """
    Claude にリクエストを送る。
    model が None または Claude Fable 5 の場合：Fable 5 を beta エンドポイントで呼び出し、
    拒否時は Opus 4.8 に自動フォールバックする（Fable 5 をユーザーが明示的に選んだ場合の経路）。
    model がそれ以外（デフォルトの Opus 4.8 等）の場合：フォールバック不要のため通常のエンドポイントで呼び出す。
    呼び出し元は常に model=st.session_state["ai_model"] を明示的に渡すため、
    この関数の model=None はライブラリとして呼ばれた場合の安全側デフォルト（Fable 5扱い）に過ぎない。
    system を省略した場合は、生成用ペルソナ（_SYSTEM）を使用する。採点等の別ペルソナが
    必要な呼び出し元は system=_SYSTEM_EVAL のように明示的に渡すこと。
    """
    sys_prompt = system if system is not None else _SYSTEM
    if model is None or model == _FABLE_MODEL:
        return client.beta.messages.create(
            model=_FABLE_MODEL,
            max_tokens=max_tokens,
            system=sys_prompt,
            messages=[{"role": "user", "content": user_msg}],
            betas=[_FALLBACK_BETA],
            fallbacks=[{"model": _FALLBACK_MODEL}],
            output_config={"effort": "high"},
        )
    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=sys_prompt,
        messages=[{"role": "user", "content": user_msg}],
        output_config={"effort": "high"},
    )


def _extract_text(msg, strip_code_fence: bool = True) -> str:
    """応答からテキストを取り出す。refusal・空応答を分かりやすいエラーに変換する。"""
    if getattr(msg, "stop_reason", None) == "refusal":
        raise ValueError("AIが安全上の理由で応答を拒否しました。内容を見直すか再試行してください。")
    text = next((b.text for b in msg.content if b.type == "text"), "")
    if not text.strip():
        raise ValueError("APIから有効なテキスト応答が返りませんでした")
    text = text.strip()
    if strip_code_fence:
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


# ================================================================
# 2段階生成 ── Step1: 留意点のみ生成（1項目ずつ個別呼び出し）
# ================================================================
def _generate_notes_single(
    target_label: str,
    all_item_labels: list,
    construction_prompt: str,
    reference_context: str = "",
    project_name: str = "",
    docs_context: str = "",
    api_key: str = None,
    model: str = None,
) -> list:
    """1つの評価項目に特化した留意点3件を生成する。1項目1呼び出しで項目間混在を防ぐ。"""
    key = api_key or _load_api_key()
    client = anthropic.Anthropic(api_key=key, timeout=300.0)

    # 全項目のリスト（他の項目との区別を明示）
    items_context = "\n".join(
        f"  {'→ 今回の生成対象' if label == target_label else '　（他の項目）　'}  項目{i+1}：「{label}」"
        for i, label in enumerate(all_item_labels)
    )

    project_block = f"【工事名】{project_name}\n\n" if project_name else ""
    docs_block    = _build_docs_block(docs_context)
    ref_block     = _build_ref_block(reference_context)
    evolve_note   = _build_evolve_note(reference_context)

    # 対象項目が何を評価するかの補足（固定分類に当てはめず、項目名の趣旨そのものに
    # 特化させる。評価項目名は案件ごとに変わる自由入力であり、特定の項目名パターンに
    # だけ対応する実装は不可のため、項目名文字列をそのまま趣旨として提示する）
    focus_hint = (
        f"「{target_label}」が評価するのは、項目名「{target_label}」が意味する事項そのものです。\n"
        f"3件の留意点はすべて「{target_label}」の趣旨の範囲内に収め、その趣旨と無関係な\n"
        f"他分野（他の評価項目が扱う観点）の話を混ぜないでください。\n"
    )

    user_msg = (
        f"以下の工事情報に基づき、評価項目「{target_label}」の留意点①②③（3件）のみを生成してください。\n\n"
        f"{project_block}"
        f"{docs_block}"
        f"{ref_block}"
        f"【施工条件プロンプト（現場担当者の補足メモ）】\n{construction_prompt}\n\n"
        f"【評価項目の全体構成（他項目との重複を避けるために参照）】\n{items_context}\n\n"
        f"【今回の生成対象】\n評価項目：「{target_label}」\n{focus_hint}\n"
        f"【厳守事項】\n"
        f"・生成する3件の留意点は、必ず「{target_label}」の趣旨・目的に直結した内容のみであること\n"
        f"・他の評価項目（{', '.join(l for l in all_item_labels if l != target_label)}）に関わる内容を混入させないこと\n"
        f"・3件はそれぞれ異なる視点・内容であること（同じ観点の言い換えは不可）\n"
        f"・各留意点は37字以内（38字以上は即失格）・「〜に留意する。」で終わること\n"
        f"・設計図書に記載された施工条件・制約・数値を具体的根拠として活用すること\n"
        f"・現場固有性は、今回の施工条件プロンプト・設計図書に実際に書かれている情報\n"
        f"  （地名・工種・地形・数量・制約・周辺条件）を引用して出すこと。\n"
        f"・【厳守】今回の資料に書かれていない工種・環境・作業（潮汐・漁業・観光・港湾・\n"
        f"  潜水士・作業船・海洋工事等）を過去提案書や一般知識から補ってはならない。\n"
        f"  今回が海洋・港湾工事でない場合、海に関する内容は一切書かないこと。\n"
        f"{evolve_note}\n\n"
        f"JSON配列のみで回答（```不要）:\n"
        f'["留意点①テキスト", "留意点②テキスト", "留意点③テキスト"]'
    )

    try:
        msg = _create_message(client, user_msg, model=model)
    except anthropic.RateLimitError:
        raise RuntimeError("APIのレート制限に達しました。しばらく待ってから再試行してください。")

    text = _extract_text(msg)
    try:
        notes = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI応答のJSON解析に失敗しました: {e}\n応答内容: {text[:200]}") from e
    if not isinstance(notes, list):
        notes = []
    while len(notes) < 3:
        notes.append("")
    return [str(n) for n in notes[:3]]


def generate_notes(item_labels: list, construction_prompt: str,
                   reference_context: str = "", project_name: str = "",
                   docs_context: str = "", api_key: str = None,
                   model: str = None) -> dict:
    """
    評価項目ごとに留意点3件のみを生成する。
    項目ごとに個別API呼び出しを行い、項目間の内容混在を防ぐ。
    Returns: {item_label: ["note1", "note2", "note3"], ...}
    """
    result = {}
    for label in item_labels:
        notes = _generate_notes_single(
            target_label=label,
            all_item_labels=item_labels,
            construction_prompt=construction_prompt,
            reference_context=reference_context,
            project_name=project_name,
            docs_context=docs_context,
            api_key=api_key,
            model=model,
        )
        result[label] = notes
    return result


# ================================================================
# 2段階生成 ── Step2: 確定した留意点に対して理由を生成
# ================================================================
def generate_all_reasons(item_labels: list, all_notes: dict,
                         construction_prompt: str,
                         reference_context: str = "", project_name: str = "",
                         docs_context: str = "", api_key: str = None,
                         model: str = None) -> dict:
    """
    確定済みの各留意点に対して「なぜその留意点が必要か」を、
    その留意点が属する評価項目名の趣旨・テーマ1本に完全特化した4つの理由で説明する。
    4つの理由は項目名の趣旨の中で互いに異なる切り口から述べ、他分野の観点を混ぜない。
    all_notes: {item_label: ["note1", "note2", "note3"], ...}
    Returns: {item_label: [[r1,r2,r3,r4], [r1,r2,r3,r4], [r1,r2,r3,r4]], ...}
    """
    key = api_key or _load_api_key()
    client = anthropic.Anthropic(api_key=key, timeout=300.0)

    items_text = "\n".join(f"- 項目{i+1}：{label}" for i, label in enumerate(item_labels))
    _ni_labels = ["①", "②", "③"]

    notes_block = ""
    for i, label in enumerate(item_labels):
        theme_hint = _get_theme_hint(label)
        notes = all_notes.get(label, ["", "", ""])
        notes_block += f"\n■ 項目{i+1}「{label}」\n"
        notes_block += f"  各留意点の理由①〜④を特化させるテーマ:\n{theme_hint}\n"
        for ni, note in enumerate(notes):
            notes_block += f"  留意点{_ni_labels[ni]}：「{note}」\n"

    json_tmpl_data = {}
    for label in item_labels:
        notes = all_notes.get(label, ["", "", ""])
        json_tmpl_data[label] = [
            {"留意点": (notes[ni] if ni < len(notes) else ""), "理由リスト": ["〜ため、〜が重要である。"] * 4}
            for ni in range(3)
        ]
    json_template = json.dumps(json_tmpl_data, ensure_ascii=False, indent=2)

    project_block = f"【工事名】{project_name}\n\n" if project_name else ""
    docs_block    = _build_docs_block(docs_context)
    ref_block     = f"\n【蓄積ナレッジ】\n{reference_context}\n" if reference_context else ""

    user_msg = (
        f"以下の各留意点に対して「なぜその留意点が必要か」を、\n"
        f"その留意点が属する評価項目名の趣旨・テーマ1本に完全特化した理由①〜④で説明してください。\n\n"
        f"{project_block}"
        f"{docs_block}"
        f"{ref_block}"
        f"【施工条件プロンプト（現場担当者の補足メモ）】\n{construction_prompt}\n\n"
        f"【評価項目（3項目・案件ごとに変わる自由入力の項目名。この項目名の趣旨に理由を特化させること）】\n{items_text}\n\n"
        f"【各留意点（確定済み）と、理由を特化させるテーマ】\n{notes_block}\n\n"
        f"【生成ルール（厳守）】\n"
        f"・各理由は「この留意点を実施する必要性・根拠」── 「なぜその留意点が必要か」を説明すること\n"
        f"・【整合性・最重要】各理由は、対応する留意点が指す具体的な行為・対象・状況を必ず受けて、\n"
        f"  「その留意点（の対応）を怠るとどうなるか／実施すると何が得られるか」を述べること。\n"
        f"  留意点の対象（工種・部位・リスク）とずれた一般論、どの留意点にも当てはまる汎用文は禁止。\n"
        f"  理由を書く前に、その留意点の核心語（対象物・行為）を1つ特定し、必ずその語に接続させること\n"
        f"・【テーマ特化・最重要】理由①〜④は必ず対応する留意点の内容を前提とし、\n"
        f"  その留意点が属する評価項目名の趣旨・テーマ1本に完全特化すること\n"
        f"  （上記「理由を特化させるテーマ」を踏まえる）。項目名の趣旨の中で切り口を変え、\n"
        f"  4方向から留意点の必要性を多角的に基礎づけること。\n"
        f"・【非越境・最重要】理由①〜④に、その項目名の趣旨と無関係な他分野の観点\n"
        f"  （安全・工程・品質・出来形・環境等のうち、その項目名の趣旨に含まれないもの）を\n"
        f"  1つも混ぜないこと。例：工程管理の項目の理由に安全・品質・出来形・環境の話を入れない。\n"
        f"・4つの理由は項目名の趣旨の中で互いに異なる切り口から述べ、同じことの言い換えは禁止\n"
        f"・各理由は、原因節を「〜ため、」で受け、文末は「〜が重要である。」「〜が必要である。」「〜が求められる。」等の結論で締める1文とすること。「〜ため、〜ため。」のように「ため」を同一文中で2回重ねる構成（ためため文）は絶対禁止。45字前後を目安に、全理由を45字に近い充実した文字数で具体的に記述すること。30字以下の短い理由は不可。45字を多少超えてもよい（Excelのはみ出しは許容）\n"
        f"・文字数を稼ぐための冗長表現は避け、具体的な工法・数値・現場状況を盛り込んで45字程度に充実させること\n"
        f"・設計図書が提供されている場合は、そこに記載された数値・条件・工法を理由の根拠として引用すること\n"
        f"・留意点のテキストをそのまま繰り返さず、なぜ必要かの因果・根拠を述べること\n"
        f"・現場固有の根拠は、今回の施工条件プロンプト・設計図書に実際に書かれた情報\n"
        f"  （地名・工種・地形・数量・制約・周辺条件）から取ること。\n"
        f"・【厳守】今回の資料に無い工種・環境・作業（潮汐・漁業・観光・港湾・潜水士・\n"
        f"  作業船・海洋工事等）を過去提案書や一般知識から補って理由に混入させないこと。\n"
        f"  今回が海洋・港湾工事でない場合、海に関する根拠は一切書かないこと。\n\n"
        f"「留意点」の値は変更せず、「理由リスト」のみを埋めてJSONで回答（```不要）:\n{json_template}"
    )

    try:
        msg = _create_message(client, user_msg, model=model)
    except anthropic.RateLimitError:
        raise RuntimeError("APIのレート制限に達しました。しばらく待ってから再試行してください。")

    text = _extract_text(msg)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI応答のJSON解析に失敗しました: {e}\n応答内容: {text[:200]}") from e

    result = {}
    for i, label in enumerate(item_labels):
        if label in data:
            entries = data[label]
        else:
            raise ValueError(f"AI応答に項目「{label}」のキーが見つかりませんでした。応答キー: {list(data.keys())}")
        reasons_list = []
        for ni in range(3):
            e = entries[ni] if ni < len(entries) else {}
            reasons = e.get("理由リスト", [])
            while len(reasons) < 4:
                reasons.append("")
            reasons_list.append([str(r) for r in reasons[:4]])
        result[label] = reasons_list

    return result


# ================================================================
# AI予想採点（STEP4：確定した留意点・理由一式を50点満点で採点）
# ================================================================
def evaluate_proposal_score(item_labels: list, all_notes: dict, all_reasons: dict,
                            construction_prompt: str, project_name: str = "",
                            docs_context: str = "", reference_context: str = "",
                            api_key: str = None, model: str = None) -> dict:
    """
    確定済みの提案書一式（全項目の留意点＋理由）を50点満点でAI採点する。
    採点は _SYSTEM_EVAL（厳格・公正な審査員ペルソナ）で行い、_SYSTEM（生成用ペルソナ）とは
    独立した観点で評価する。

    all_notes:   {item_label: ["note1", "note2", "note3"], ...}
    all_reasons: {item_label: [[r1,r2,r3,r4], [r1,r2,r3,r4], [r1,r2,r3,r4]], ...}

    Returns:
      {
        "total_score": int, "max_score": 50,
        "guidance_message": str,
        "item_scores": [{"item": str, "score": int, "max": int, "comment": str}, ...],
        "overall": {"score": int, "max": int, "comment": str},
        "strengths": [str, ...],
        "improvements": [str, ...],
        "revision_instructions": [
            {"item": str, "target": str, "current_text": str, "suggested_text": str, "reason": str}, ...
        ],
      }
    """
    key = api_key or _load_api_key()
    client = anthropic.Anthropic(api_key=key, timeout=300.0)

    _ni_labels = ["①", "②", "③"]
    _ri_labels = ["①", "②", "③", "④"]

    proposal_block = ""
    for i, label in enumerate(item_labels):
        notes = all_notes.get(label, ["", "", ""])
        reasons = all_reasons.get(label, [["", "", "", ""]] * 3)
        proposal_block += f"\n■ 評価項目{i+1}「{label}」\n"
        for ni in range(3):
            note = notes[ni] if ni < len(notes) else ""
            r4 = reasons[ni] if ni < len(reasons) else ["", "", "", ""]
            proposal_block += f"  留意点{_ni_labels[ni]}：「{note}」\n"
            for ri, r in enumerate(r4):
                if ri < len(_ri_labels):
                    proposal_block += f"    理由{_ri_labels[ri]}：「{r}」\n"

    project_block = f"【工事名】{project_name}\n\n" if project_name else ""
    docs_block    = _build_docs_block(docs_context)
    ref_block     = f"\n【蓄積ナレッジ：過去の提出済み提案書】\n{reference_context}\n" if reference_context else ""

    json_tmpl = json.dumps(
        {
            "total_score": 0,
            "max_score": 50,
            "guidance_message": "",
            "item_scores": [
                {"item": label, "score": 0, "max": 15, "comment": ""} for label in item_labels
            ],
            "overall": {"score": 0, "max": 5, "comment": ""},
            "strengths": [],
            "improvements": [],
            "revision_instructions": [
                {"item": "", "target": "", "current_text": "", "suggested_text": "", "reason": ""}
            ],
        },
        ensure_ascii=False, indent=2,
    )

    user_msg = (
        f"以下の技術提案書（様式４・確定版）を、審査員として厳格かつ公正に50点満点で採点してください。\n\n"
        f"{project_block}"
        f"{docs_block}"
        f"{ref_block}"
        f"【施工条件プロンプト（現場担当者の補足メモ）】\n{construction_prompt}\n\n"
        f"【採点対象：確定済みの提案書一式】{proposal_block}\n"
        f"【採点ルール（厳守）】\n"
        f"・甘い加点はしないこと。平凡な内容は満点にしないこと\n"
        f"・根拠のない減点はしないこと。実際の文章上の問題点のみを減点理由とすること\n"
        f"・各項目のスコアには、具体的な根拠（該当箇所の引用・要約）を必ず添えること\n"
        f"・improvements は「どの留意点・理由の、どの部分を、どう直すべきか」が\n"
        f"  分かる実務的な指摘にすること（抽象的な助言は不可）\n"
        f"・revision_instructions には、減点要因があった留意点・理由について、\n"
        f"  current_text（現状の文章）と suggested_text（そのまま差し替え可能な修正後の\n"
        f"  完成文）を対で示すこと。suggested_text は文字数制約（留意点37字以内／\n"
        f"  理由45字前後・30字以下不可）を満たす完成文とし、抽象的な助言は書かないこと\n"
        f"・guidance_message には、採点者自身の言葉で、この提案書全体への総評と\n"
        f"  最優先で直すべき点を、実務者に語りかける口調で200〜400字程度で書くこと\n"
        f"・total_score は item_scores の score 合計 + overall.score と必ず一致させること\n\n"
        f"以下の形式のJSONのみで回答してください（```不要、item_scores は入力順のまま{len(item_labels)}件）:\n{json_tmpl}"
    )

    try:
        msg = _create_message(client, user_msg, model=model, system=_SYSTEM_EVAL)
    except anthropic.RateLimitError:
        raise RuntimeError("APIのレート制限に達しました。しばらく待ってから再試行してください。")

    text = _extract_text(msg)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI応答のJSON解析に失敗しました: {e}\n応答内容: {text[:200]}") from e

    # ── 正規化・防御的な補完
    item_scores_raw = data.get("item_scores", [])
    item_scores = []
    for i, label in enumerate(item_labels):
        e = item_scores_raw[i] if i < len(item_scores_raw) else {}
        item_scores.append({
            "item": str(e.get("item", label)) or label,
            "score": int(e.get("score", 0) or 0),
            "max": int(e.get("max", 15) or 15),
            "comment": str(e.get("comment", "")),
        })

    overall_raw = data.get("overall", {}) or {}
    overall = {
        "score": int(overall_raw.get("score", 0) or 0),
        "max": int(overall_raw.get("max", 5) or 5),
        "comment": str(overall_raw.get("comment", "")),
    }

    computed_total = sum(s["score"] for s in item_scores) + overall["score"]
    total_score = data.get("total_score")
    try:
        total_score = int(total_score)
    except (TypeError, ValueError):
        total_score = computed_total
    # AI側の合計値がずれている場合は内訳から再計算した値を優先する
    if total_score != computed_total:
        total_score = computed_total

    # revision_instructions：欠損・型不正時も落ちないよう防御的にパースする
    revision_instructions_raw = data.get("revision_instructions") or []
    revision_instructions = []
    if isinstance(revision_instructions_raw, list):
        for e in revision_instructions_raw:
            if not isinstance(e, dict):
                continue
            current_text = str(e.get("current_text", "") or "")
            suggested_text = str(e.get("suggested_text", "") or "")
            # current_text・suggested_text のいずれも空の項目は意味を成さないため除外
            if not current_text.strip() and not suggested_text.strip():
                continue
            revision_instructions.append({
                "item": str(e.get("item", "") or ""),
                "target": str(e.get("target", "") or ""),
                "current_text": current_text,
                "suggested_text": suggested_text,
                "reason": str(e.get("reason", "") or ""),
            })

    guidance_message = str(data.get("guidance_message", "") or "")

    return {
        "total_score": total_score,
        "max_score": int(data.get("max_score", 50) or 50),
        "guidance_message": guidance_message,
        "item_scores": item_scores,
        "overall": overall,
        "strengths": [str(s) for s in (data.get("strengths") or [])],
        "improvements": [str(s) for s in (data.get("improvements") or [])],
        "revision_instructions": revision_instructions,
    }


# ================================================================
# 理由のみ再生成
# ================================================================
def generate_reasons(chui_text: str, item_label: str, all_item_labels: list,
                     construction_prompt: str, reference_context: str = "",
                     project_name: str = "", docs_context: str = "",
                     api_key: str = None, model: str = None) -> list:
    """
    指定した留意点に対して理由①〜④を4つ生成する。
    4つの理由は、その留意点が属する評価項目名の趣旨・テーマ1本に完全特化させ、
    項目名の趣旨の中で互いに異なる切り口から述べる（他分野の観点を混ぜない）。
    Returns: [理由①, 理由②, 理由③, 理由④]
    """
    key = api_key or _load_api_key()
    client = anthropic.Anthropic(api_key=key, timeout=300.0)

    items_text = "\n".join(f"- 項目{i+1}：{label}" for i, label in enumerate(all_item_labels))
    theme_hint = _get_theme_hint(item_label)

    project_block = f"【工事名】{project_name}\n\n" if project_name else ""
    docs_block    = _build_docs_block(docs_context)
    ref_block     = f"\n【蓄積ナレッジ：過去の提出済み提案書】\n{reference_context}\n\n" if reference_context else ""

    user_msg = (
        f"以下の留意点に対して「なぜその留意点が必要か」を、\n"
        f"評価項目名「{item_label}」の趣旨・テーマ1本に完全特化した理由①〜④で説明してください。\n\n"
        f"{project_block}"
        f"{docs_block}"
        f"{ref_block}"
        f"【施工条件プロンプト（現場担当者の補足メモ）】\n{construction_prompt}\n\n"
        f"【評価項目（3項目・案件ごとに変わる自由入力の項目名）】\n{items_text}\n\n"
        f"【対象評価項目（この項目名の趣旨に理由を特化させること）】\n{item_label}\n\n"
        f"【留意点（この内容がなぜ必要かを「{item_label}」の趣旨の中で多角的に説明すること）】\n「{chui_text}」\n\n"
        f"【理由①〜④を特化させるテーマ】\n{theme_hint}\n\n"
        f"【生成ルール（厳守）】\n"
        f"・各理由は「この留意点を実施する必要性・根拠」── 「なぜ『{chui_text}』が必要か」を説明すること\n"
        f"・【テーマ特化・最重要】理由①〜④は、評価項目名「{item_label}」の趣旨・テーマ1本に\n"
        f"  完全特化すること。項目名の趣旨の中で切り口を変え、4方向から留意点の必要性を\n"
        f"  多角的に基礎づける。4つは互いに異なる切り口から述べ、同じことの言い換えは禁止\n"
        f"・【非越境・最重要】理由①〜④に、「{item_label}」の趣旨と無関係な他分野の観点\n"
        f"  （安全・工程・品質・出来形・環境等のうち、この項目名の趣旨に含まれないもの）を\n"
        f"  1つも混ぜないこと。「{item_label}」が意味する範囲の話だけで4つを構成すること。\n"
        f"・【整合性・最重要】4つの理由はすべて、この留意点『{chui_text}』が指す具体的な対象・行為を必ず受けて、\n"
        f"  それを怠ると生じる不都合／実施して得られる効果を述べること。留意点の対象とずれた一般論・\n"
        f"  どの留意点にも使える汎用文は禁止。留意点の核心語（対象物・行為）を特定し必ずその語に接続させること\n"
        f"・設計図書が提供されている場合は、そこに記載された数値・条件・工法を理由の根拠として引用すること\n"
        f"・各理由は、原因節を「〜ため、」で受け、文末は「〜が重要である。」「〜が必要である。」「〜が求められる。」等の結論で締める1文とすること。「〜ため、〜ため。」のように「ため」を同一文中で2回重ねる構成（ためため文）は絶対禁止。45字前後を目安に、全理由を45字に近い充実した文字数で具体的に記述すること。30字以下の短い理由は不可。45字を多少超えてもよい（Excelのはみ出しは許容）\n"
        f"・文字数を稼ぐための冗長表現は避け、具体的な工法・数値・現場状況を盛り込んで45字程度に充実させること\n"
        f"・留意点のテキストをそのまま繰り返さず、なぜ必要かの因果・根拠を述べること\n"
        f"・現場固有の根拠は、今回の施工条件プロンプト・設計図書に実際に書かれた情報\n"
        f"  （地名・工種・地形・数量・制約・周辺条件）から取ること。\n"
        f"・【厳守】今回の資料に無い工種・環境・作業（潮汐・漁業・観光・港湾・潜水士・\n"
        f"  作業船・海洋工事等）を過去提案書や一般知識から補って理由に混入させないこと。\n"
        f"  今回が海洋・港湾工事でない場合、海に関する根拠は一切書かないこと。\n"
        f"・JSONの配列のみで回答（説明文・```不要）\n\n"
        f'["理由①テキスト", "理由②テキスト", "理由③テキスト", "理由④テキスト"]'
    )

    try:
        msg = _create_message(client, user_msg, model=model)
    except anthropic.RateLimitError:
        raise RuntimeError("APIのレート制限に達しました。しばらく待ってから再試行してください。")

    text = _extract_text(msg)

    try:
        reasons = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI応答のJSON解析に失敗しました: {e}\n応答内容: {text[:200]}") from e
    if not isinstance(reasons, list):
        reasons = []
    while len(reasons) < 4:
        reasons.append("")
    reasons = [str(r) for r in reasons[:4]]
    return reasons


# ================================================================
# 代替留意点の生成（別の候補差し替え用）
# ================================================================
def generate_alternative_notes(
    item_label: str,
    all_item_labels: list,
    construction_prompt: str,
    existing_notes: list = None,
    reference_context: str = "",
    project_name: str = "",
    docs_context: str = "",
    api_key: str = None,
    count: int = 6,
    model: str = None,
) -> list:
    """
    指定評価項目に対して代替の留意点を count 件生成する。
    Returns: [{"留意点": str}, ...]
    """
    key = api_key or _load_api_key()
    client = anthropic.Anthropic(api_key=key, timeout=300.0)

    items_text = "\n".join(f"- 項目{i+1}：{label}" for i, label in enumerate(all_item_labels))

    existing_block = ""
    if existing_notes:
        used = [n for n in existing_notes if n and n.strip()]
        if used:
            existing_block = "\n【既に使用中の留意点（これらと重複しないこと）】\n" + "\n".join(f"- {n}" for n in used)

    project_block = f"【工事名】{project_name}\n\n" if project_name else ""
    docs_block    = _build_docs_block(docs_context)
    ref_block     = f"\n【蓄積ナレッジ：過去の提出済み提案書】\n{reference_context}\n" if reference_context else ""

    user_msg = (
        f"以下の評価項目と工事情報に基づき、「{item_label}」の代替留意点を{count}件生成してください。\n\n"
        f"{project_block}"
        f"{docs_block}"
        f"{ref_block}"
        f"【施工条件プロンプト（現場担当者の補足メモ）】\n{construction_prompt}\n\n"
        f"【評価項目（3項目）】\n{items_text}\n\n"
        f"【対象評価項目】：{item_label}\n"
        f"{existing_block}\n\n"
        f"【生成ルール（厳守）】\n"
        f"・各留意点は「〜に留意する。」で終わる1文\n"
        f"・37字以内（38字以上は即失格のため絶対厳守）\n"
        f"・{count}件それぞれ視点・内容が重複しないこと\n"
        f"・評価項目「{item_label}」の趣旨と完全に合致した内容にすること\n"
        f"・設計図書が提供されている場合は、そこに記載された施工条件・制約・数値を積極的に盛り込むこと\n"
        f"・現場固有性は、今回の施工条件プロンプト・設計図書に実際に書かれている情報から出すこと\n"
        f"・【厳守】今回の資料に無い工種・環境・作業（潮汐・漁業・観光・港湾・潜水士・\n"
        f"  作業船・海洋工事等）を過去提案書や一般知識から補ってはならない。今回が海洋・\n"
        f"  港湾工事でない場合、海に関する内容は一切書かないこと。\n"
        f"・JSONの配列のみで回答（説明文・```不要）\n\n"
        f'["留意点①テキスト", "留意点②テキスト", ...]'
    )

    try:
        msg = _create_message(client, user_msg, model=model)
    except anthropic.RateLimitError:
        raise RuntimeError("APIのレート制限に達しました。しばらく待ってから再試行してください。")

    text = _extract_text(msg)

    try:
        notes_list = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI応答のJSON解析に失敗しました: {e}\n応答内容: {text[:200]}") from e
    if not isinstance(notes_list, list):
        notes_list = []
    return [{"留意点": str(n)} for n in notes_list[:count] if str(n).strip()]


# ================================================================
# メイン生成（後方互換・フォールバック用）
# ================================================================
def generate(item_labels: list, construction_prompt: str,
             reference_context: str = "", project_name: str = "",
             docs_context: str = "", api_key: str = None,
             model: str = None) -> dict:
    """評価項目3つ + 施工条件プロンプトから留意点・理由を生成する。"""
    key = api_key or _load_api_key()
    client = anthropic.Anthropic(api_key=key, timeout=300.0)

    items_text = "\n".join(f"- 項目{i+1}：{label}" for i, label in enumerate(item_labels))
    theme_block = "\n".join(
        f"\n【{label} の理由①〜④を特化させるテーマ】\n{_get_theme_hint(label)}"
        for label in item_labels
    )
    json_template = json.dumps(
        {label: [{"留意点": "〜に留意する。", "理由リスト": ["〜ため、〜が重要である。"] * 4}] * 3
         for label in item_labels},
        ensure_ascii=False, indent=2
    )

    project_block = f"【工事名】{project_name}\n\n" if project_name else ""
    docs_block    = _build_docs_block(docs_context)
    ref_block     = _build_ref_block(reference_context)
    evolve_note   = _build_evolve_note(reference_context)

    user_msg = (
        f"以下の工事情報に基づき、様式４技術提案書を生成してください。\n\n"
        f"{project_block}"
        f"{docs_block}"
        f"{ref_block}"
        f"【施工条件プロンプト（現場担当者の補足メモ）】\n{construction_prompt}\n\n"
        f"【評価項目（3項目・案件ごとに変わる自由入力の項目名。この項目名の趣旨に理由を特化させること）】\n{items_text}\n\n"
        f"【生成ルール（厳守）】\n"
        f"・各項目につき留意点①②③（3つ）を生成する\n"
        f"・各留意点につき理由①②③④（4つ）を生成する\n"
        f"・留意点は必ず37字以内（38字以上は即失格のため絶対厳守）\n"
        f"・各留意点の4つの理由は、その留意点が属する評価項目名の趣旨・テーマ1本に完全特化し、項目名の趣旨の中で互いに異なる4つの切り口から多角的に構成する\n"
        f"・【非越境】4つの理由に、その項目名の趣旨と無関係な他分野の観点（安全・工程・品質・出来形・環境等のうち項目名の趣旨に含まれないもの）を1つも混ぜない（例：工程管理の理由に安全・品質の話を入れない）\n"
        f"・各理由は40字以内（厳守）── Excelは10pt固定でフォント縮小しないため40字超はセルからはみ出す\n"
        f"・同じ評価項目の3つの留意点は互いに視点・内容が重複しないようにする\n"
        f"{theme_block}\n"
        f"{evolve_note}\n\n"
        f"以下の形式のJSONのみで回答してください（```不要）:\n{json_template}"
    )

    try:
        msg = _create_message(client, user_msg, model=model)
    except anthropic.RateLimitError:
        raise RuntimeError("APIのレート制限に達しました。しばらく待ってから再試行してください。")

    text = _extract_text(msg)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI応答のJSON解析に失敗しました: {e}\n応答内容: {text[:200]}") from e

    result = {}
    for label in item_labels:
        entries = data.get(label, [])
        normalized = []
        for i in range(3):
            e = entries[i] if i < len(entries) else {}
            reasons = e.get("理由リスト", [])
            while len(reasons) < 4:
                reasons.append("")
            normalized.append({
                "留意点": e.get("留意点", ""),
                "理由リスト": reasons[:4],
            })
        result[label] = normalized
    return result


# ================================================================
# 工事資料からプロンプト自動生成
# ================================================================
def generate_prompt_from_docs(docs_context: str, project_name: str = "",
                               api_key: str = None, model: str = None) -> str:
    """工事資料を解析して施工条件プロンプトを自動生成する。"""
    key = api_key or _load_api_key()
    client = anthropic.Anthropic(api_key=key, timeout=300.0)

    project_block = f"【工事名】{project_name}\n\n" if project_name else ""
    docs_block = _build_docs_block(docs_context)

    user_msg = (
        f"以下の工事資料を読み込み、技術提案書（様式４）の留意点生成に使う施工条件プロンプトを作成してください。\n\n"
        f"{project_block}"
        f"{docs_block}\n"
        f"【作成ルール】\n"
        f"・【最重要】この工事資料に実際に書かれている事実のみを記述すること。資料に無い\n"
        f"  工種・環境・作業（潮汐・漁業・観光・海水浴場・港湾・潜水作業・作業船・海洋工事\n"
        f"  等）を推測や一般知識で補ってはならない。この工事が海岸・港湾・水域を伴わない\n"
        f"  （山間部・道路・河川・造成・陸上等の）工事なら、海に関する語を一切書かないこと。\n"
        f"・工事の概要（場所・工種・使用機械・数量）を資料に基づいて含めること\n"
        f"・周辺環境の制約は、資料から読み取れるもののみ含めること（該当する場合の例：\n"
        f"  交通・近隣住民・河川・農地・漁業・観光等。資料に無いものは書かない）\n"
        f"・施工上の特殊条件は、資料から読み取れるもののみ含めること（該当する場合の例：\n"
        f"  季節・気象・地形・地質・搬入路・仮設・潮汐・浅水域等。資料に無いものは書かない）\n"
        f"・安全管理上の重要事項も、資料から読み取れるもののみ含めること\n"
        f"・150〜250字程度の日本語文章（箇条書き不可・体言止め可・文章形式）\n"
        f"・このプロンプト自体が、後続の留意点・理由生成の精度を左右する入力情報になる。\n"
        f"  抽象的な要約ではなく、設計図書中の固有名詞・数値・制約条件をできる限り\n"
        f"  具体的に盛り込み、情報密度の高い文章にすること\n\n"
        f"プロンプト文章のみを出力してください（タイトル・説明・記号は不要）："
    )

    try:
        msg = _create_message(client, user_msg, model=model)
    except anthropic.RateLimitError:
        raise RuntimeError("APIのレート制限に達しました。しばらく待ってから再試行してください。")

    return _extract_text(msg, strip_code_fence=False)
