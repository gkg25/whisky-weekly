# Whisky Weekly

ウイスキー業界紙風のニュースレターPDFを **毎週月曜 朝7時（日本時間）** に Google の Gemini で要約し、Gmail で自分宛に自動配信するアプリケーション。

業界紙『酒販ニュース』のフォーマットを参考に、ウイスキー業界（国内＋海外）に特化したコンテンツを生成する。

## 月額ランニングコスト：**0円**

| 用途 | サービス | 課金 |
|---|---|---|
| LLM（要約・翻訳） | Google Gemini API 無料枠（gemini-2.5-flash / flash-lite） | 無料 |
| 実行環境（週1回） | GitHub Actions（Public リポジトリ） | 無料 |
| メール送信 | Gmail SMTP（アプリパスワード認証） | 無料 |
| ニュース収集 | 一次ソース RSS / Google ニュース RSS / HTML スクレイピング | 無料 |
| 日本語フォント | Noto Sans JP / Noto Serif JP（Google Fonts, OFL） | 無料 |

## 機能

- 32本の検索クエリ（市場・経済データ・製造技術・新商品・規制・原料を網羅）で広く収集
- RSS が無いサイトは Google ニュース RSS で補完
- URL正規化＋タイトル類似度で重複排除
- 既出URLは `data/seen_urls.json` で記録、翌週以降は除外
- Gemini で日本語要約・カテゴリ分類・重要度スコアリング
- ハルシネーション対策プロンプト（記事本文外の情報は出力禁止）
- 「常設記事・過去ニュース再掲」を自動検出してスコア低下
- A4縦・横書き・日本語フォントの業界紙風 PDF を Playwright（Chromium）でレンダリング
- Gmail SMTP（アプリパスワード認証）で PDF 添付メール送信

## ディレクトリ構成

```
whisky-weekly/
├── .github/workflows/weekly.yml      # GitHub Actions（毎週月曜7:00 JST）
├── src/
│   ├── main.py                       # パイプライン統合エントリ
│   ├── config.py                     # ソース一覧・検索クエリ
│   ├── collectors/
│   │   ├── base.py                   # Article データクラス・ユーティリティ
│   │   ├── rss_collector.py          # 一次ソース RSS 収集
│   │   ├── google_news_collector.py  # Google ニュース RSS 収集
│   │   └── html_collector.py         # HTML スクレイピング（補助）
│   ├── llm/
│   │   └── gemini_client.py          # Gemini クライアント（リトライ・レート制御）
│   ├── summarizer.py                 # 要約モジュール（プロンプト含む）
│   ├── deduplicator.py               # 重複排除
│   ├── pdf_builder.py                # PDF 生成
│   ├── mailer.py                     # Gmail SMTP 送信
│   └── templates/
│       ├── newsletter.html           # PDF テンプレート（Jinja2）
│       └── style.css                 # スタイル
├── data/
│   ├── issue_counter.json            # 号数管理
│   └── seen_urls.json                # 既出URL記録
├── output/                           # 生成された PDF・JSON
├── requirements.txt
├── .env.example
└── README.md
```

## 事前準備

| 項目 | 取得方法 | 費用 |
|---|---|---|
| Python 3.11+ | https://www.python.org/downloads/ から本体DL（インストール時「Add to PATH」必須） | 無料 |
| Gemini API キー | https://aistudio.google.com/ → 「Get API key」 | 無料 |
| Gmail アプリパスワード | https://myaccount.google.com/apppasswords（2段階認証必須） | 無料 |
| GitHub アカウント | https://github.com/ で作成（リポジトリは Public 推奨：Actions が完全無料） | 無料 |

## セットアップ（ローカル）

### Windows / PowerShell

```powershell
# 1. プロジェクトディレクトリに移動
cd G:\マイドライブ\whisky-weekly

# 2. 仮想環境作成（py は Windows 同梱の Python ランチャー）
py -m venv .venv

# 3. 仮想環境を有効化
.venv\Scripts\Activate.ps1

# 4. パッケージインストール
pip install -r requirements.txt

# 5. Playwright で Chromium をインストール（初回のみ・約150MB）
playwright install chromium

# 6. 環境変数ファイル準備
copy .env.example .env
notepad .env
# .env に GEMINI_API_KEY, GMAIL_APP_PASSWORD を貼り付け
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
$EDITOR .env
```

## 実行方法

### ① 自動配信（GitHub Actions）

push 後、毎週月曜 7:00 JST に自動実行。何もしなくてOK。

### ② 手動実行（特定期間）

```powershell
# 仮想環境を有効化した状態で
python -m src.main --from 2026-05-01 --to 2026-05-15 --send
```

| オプション | 説明 |
|---|---|
| `--from YYYY-MM-DD` | 必須。収集開始日 |
| `--to YYYY-MM-DD` | 必須。収集終了日 |
| `--send` | 指定すると PDF をメール送信。未指定なら生成のみ |
| `--max N` | PDF掲載最大記事数（デフォルト50） |
| `--min-score N` | 掲載基準の重要度（デフォルト4） |
| `--summarize-limit N` | Gemini 要約する最大記事数（デフォルト80） |
| `--no-advance-counter` | 号数を進めない（テスト用） |
| `--no-update-seen` | 既出URL記録を更新しない（テスト用） |
| `--verbose` | 詳細ログ |

### ③ 段階的に実行（モジュール単位、デバッグ用）

```powershell
# 収集だけ
python -m src.collectors --from 2026-05-01 --to 2026-05-26 --out output\collected.json

# 重複排除
python -m src.deduplicator --in output\collected.json --out output\deduped.json

# 要約（30件のみ）
python -m src.summarizer --in output\deduped.json --out output\summarized.json --limit 30

# PDF
python -m src.pdf_builder --in output\summarized.json --out output\test.pdf --issue 1 --period-start 2026-05-01 --period-end 2026-05-26

# メール（添付ファイル指定）
python -m src.mailer --subject "テスト" --body "ボディ" --attach output\test.pdf
```

## GitHub Actions デプロイ手順

### ① リポジトリ作成

GitHub で **Public リポジトリ**（例：`whisky-weekly`）を新規作成（Public にすると Actions が完全無料）。

### ② このプロジェクトを push

```powershell
cd G:\マイドライブ\whisky-weekly
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/whisky-weekly.git
git push -u origin main
```

⚠ `.env`（実際の鍵が入っているファイル）は `.gitignore` で除外されているので絶対に push されない。

### ③ GitHub Secrets を設定

リポジトリのページで **Settings** → **Secrets and variables** → **Actions** → **New repository secret** で4つ追加：

| Name | Value |
|---|---|
| `GEMINI_API_KEY` | `.env` の `GEMINI_API_KEY` と同じ値 |
| `GMAIL_ADDRESS` | `tomoko@gakkogawa.com` |
| `GMAIL_APP_PASSWORD` | `.env` の `GMAIL_APP_PASSWORD` と同じ値（16文字、空白なし） |
| `RECIPIENT_EMAIL` | `tomoko@gakkogawa.com` |

### ④ ワークフロー初回手動実行（動作確認）

リポジトリの **Actions** タブ → **Whisky Weekly** → **Run workflow**

- `from_date`、`to_date` は空欄で OK（自動的に過去7日になる）
- 「Run workflow」をクリック

→ 数分後に GitHub Actions が走り、`tomoko@gakkogawa.com` に PDF が届く。

### ⑤ 以降は自動

何もしなければ毎週月曜 7:00 JST に自動配信される。

## 環境変数

`.env`（ローカル）または GitHub Secrets（CI）で設定：

| Name | 説明 |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio で取得 |
| `GMAIL_ADDRESS` | 送信元 Gmail アドレス |
| `GMAIL_APP_PASSWORD` | Gmail アプリパスワード（16文字、空白なし） |
| `RECIPIENT_EMAIL` | 受信先メールアドレス。カンマ区切りで複数指定可（BCC一括送信） |
| `GEMINI_MODEL`（任意） | デフォルト `gemini-2.5-flash-lite`。`gemini-2.5-flash` 等に変更可 |

## ハルシネーション対策

LLM（Gemini）の自動生成には誤情報リスクがあるため、以下の設計で対策：

- 各記事は一次ソース本文のみを根拠に要約（Gemini に「テキストに書かれていない情報は出力禁止」を明示）
- 数字・固有名詞・日付は原文ママで抽出（key_facts に列挙）
- 全記事に出典URL・媒体名・公開日を併記
- Google ニュース RSS の URL（`https://news.google.com/rss/articles/...`）はクリック時にブラウザ側の JS リダイレクトで原典に遷移
- 「常設記事・過去ニュース再掲・ブランド総合紹介」を Gemini が検出して relevance_score を下げる（PDFに掲載されない）
- 取得失敗・内容曖昧な記事は本文非掲載、PDFの「未確認情報」セクションに URL のみ列挙（実装中）

## 複数人配信（BCC方式）

受信者を追加したい場合は `.env` および GitHub Secrets の `RECIPIENT_EMAIL` をカンマ区切りで更新する：

```
RECIPIENT_EMAIL=tomoko@gakkogawa.com, satou@gakkogawa.com, suzuki@gakkogawa.com
```

- 各受信者の To 欄には **送信者本人** だけが見え、他の受信者はお互いに見えない（BCC方式）
- 5〜10人程度なら C案で十分。20人を超える運用は Google Workspace グループ（A案）への移行を推奨

新規希望者が来たときの運用：
1. メアド確認
2. `.env` ローカルファイルにアドレス追加
3. GitHub リポジトリの Settings → Secrets → `RECIPIENT_EMAIL` を同じ値で更新
4. 翌週月曜から自動配信に反映

## トラブルシューティング

### `python` コマンドが見つからない（Windows）

→ Python 公式インストーラ実行時に「Add python.exe to PATH」のチェックを忘れた可能性。`py` ランチャーで代用するか、インストーラを再実行して `Modify` → `Add Python to environment variables` にチェック。

### Gemini が `429 Quota exceeded` を返す

→ 無料枠の上限に到達。1日待つか、`.env` の `GEMINI_MODEL` を `gemini-2.5-flash-lite` 等のライト系モデルに切り替えると別Quotaで動く可能性あり。

### Playwright が動かない

→ `playwright install chromium` を再実行。Windows で SSL エラーが出る場合は企業ネットワーク等が干渉している可能性あり。

### Gmail 送信が `SMTPAuthenticationError`

→ アプリパスワードを再発行し `.env` を更新（空白を入れない、16文字）。2段階認証が有効になっている必要あり。

### RSS から記事が取れない

→ RSSフィードは「最新20〜50件」しか保持しないため、対象期間が古いとヒットしない（正常動作）。Google ニュース RSS が補完する。

## ライセンス

社内利用（月光川蒸留所株式会社）。

## 免責

本ニュースレターは Google Gemini が公開情報をもとに自動生成しています。引用・転載前に必ず原典をご確認ください。要約に誤りが含まれる可能性があります。

## 開発進捗

- [x] Step 1: プロジェクト雛形
- [x] Step 2: 収集モジュール（RSS / Google News / HTML）
- [x] Step 3: 重複排除
- [x] Step 4: Gemini 要約・翻訳
- [x] Step 5: PDF 生成（Playwright）
- [x] Step 6: サンプル号生成＆配信
- [x] Step 7: Gmail SMTP 送信モジュール
- [x] Step 8: GitHub Actions ワークフロー
- [x] Step 9: README・運用手順
