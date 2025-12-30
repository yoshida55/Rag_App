# プロジェクト構造マップ

> 🎯 **このファイルの目的**: どこが本丸のファイルかを明記し、無駄なファイル探索を防ぐ

---

## 🚀 最初に読むべきファイル（本丸）

### ⚙️ エントリーポイント

- **`app.py`** - アプリケーション起動ファイル（検索ページへ自動遷移）

---

### 🏗️ コアロジック (`modules/`)

| ファイル              | 役割                                        |
| --------------------- | ------------------------------------------- |
| `embedding.py`        | Gemini Embedding（テキスト → ベクトル変換） |
| `database.py`         | ChromaDB 操作（類似度検索）                 |
| `llm.py`              | Gemini LLM（AI 回答・図解生成）             |
| `data_manager.py`     | practices.json CRUD + Drive 同期            |
| `answer_cache.py`     | 回答キャッシュ（類似度 85%マッチング）      |
| `drive_manager.py`    | Google Drive 同期                           |
| `learning_manager.py` | 学習進捗管理                                |
| `usage_tracker.py`    | API 使用量ログ                              |
| `ai_formatter.py`     | テキスト整形・チェック                      |

---

### 🎨 ページファイル (`pages/`)

| ファイル             | 機能                                | 行数     |
| -------------------- | ----------------------------------- | -------- |
| `1_🔍_検索.py`       | **メイン検索** + AI 回答 + 図解表示 | ~1300 行 |
| `2_📝_登録.py`       | 新規データ登録                      | ~230 行  |
| `3_📋_一覧.py`       | データ一覧・管理                    | ~760 行  |
| `4_📥_一括登録.py`   | 一括インポート                      | ~430 行  |
| `5_⚙️_設定.py`       | 設定・使用量表示                    | ~150 行  |
| `6_🧠_記憶.py`       | 学習リスト管理                      | ~200 行  |
| `7_📖_コード学習.py` | コード学習 + AI 質問                | ~750 行  |

---

### ⚙️ 設定ファイル

| ファイル                   | 内容                              |
| -------------------------- | --------------------------------- |
| `config/settings.py`       | カテゴリ、定数、GEMINI モデル設定 |
| `secrets/.env`             | API キー（gitignore 対象）        |
| `secrets/credentials.json` | Google OAuth2 認証情報            |
| `requirements.txt`         | Python 依存パッケージ             |

---

## 📁 読まなくていいフォルダ（絶対に全探索禁止）

❌ **`venv/`** - Python 仮想環境（完全無視）
❌ **`Troubleshooting/`** - 過去の問題記録（**Grep 検索のみ**）
❌ **`__pycache__/`** - Python キャッシュ（完全無視）
❌ **`bkup/`** - バックアップフォルダ（完全無視）
❌ **`uploads/`** - アップロードファイル（完全無視）
❌ **`.git/`** - Git 管理情報（完全無視）
❌ **`node_modules/`** - 依存ライブラリ（完全無視）
❌ **`*.log`** - ログファイル（完全無視）

---

## 🗂️ ディレクトリ構造

```
80_RAG/
├── app.py                    # エントリーポイント
├── config/
│   └── settings.py           # 設定・定数
├── modules/
│   ├── embedding.py          # Embedding生成
│   ├── database.py           # ChromaDB
│   ├── llm.py                # LLM呼び出し
│   ├── data_manager.py       # データ管理
│   ├── answer_cache.py       # 回答キャッシュ
│   ├── drive_manager.py      # Drive同期
│   ├── learning_manager.py   # 学習進捗
│   ├── usage_tracker.py      # 使用量追跡
│   └── ai_formatter.py       # AI整形
├── pages/
│   ├── 1_🔍_検索.py
│   ├── 2_📝_登録.py
│   ├── 3_📋_一覧.py
│   ├── 4_📥_一括登録.py
│   ├── 5_⚙️_設定.py
│   ├── 6_🧠_記憶.py
│   └── 7_📖_コード学習.py
├── data/
│   ├── practices.json        # メインデータ
│   ├── answer_cache.json     # AIキャッシュ
│   ├── learning_progress.json
│   └── images/               # アップロード画像
├── secrets/                  # 認証情報（gitignore）
├── docs/                     # 仕様書
└── CLAUDE.md                 # AI向けドキュメント
```

---

## 🎯 よくある質問

### Q1: 新機能を追加したい時、どこを見ればいい？

**A1**:

- UI 追加 → `pages/` 配下
- ロジック追加 → `modules/` 配下
- 設定変更 → `config/settings.py`

### Q2: エラーが出た時の調べ方は？

**A2**:

1. まず `grep -r "エラーキーワード" Troubleshooting/`
2. 該当ファイル 1-2 個だけ読む
3. 見つからない場合、新規問題記録を作成

### Q3: API キーはどこで管理？

**A3**:

- `secrets/.env` ファイルで一元管理
- **絶対にハードコーディングしない**

### Q4: どこから読み始めればいい？

**A4**:

1. `PROJECT_MAP.md` (このファイル) で全体像把握
2. `CLAUDE.md` で詳細仕様確認
3. `app.py` → 目的のページファイルへ

---

## 📝 メンテナンス時の注意

### 新機能追加時

1. 該当するファイルだけ修正
2. この PROJECT_MAP.md も更新
3. Troubleshooting/に問題記録（必要時）

### デバッグ時

1. エラーログ確認
2. Troubleshooting/ で Grep 検索
3. 該当ファイルのみ読む（全探索禁止）

### リファクタリング時

1. 影響範囲を機能別マップで確認
2. 関連ファイルだけ修正
3. PROJECT_MAP.md を必ず更新

---

**🎯 重要**: このファイルは常に最新状態に保つこと！新機能追加・ファイル構成変更時は必ず更新！

**最終更新**: 2024-12
