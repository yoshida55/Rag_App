# 変数名変更が不完全でエラー発生

**日付**: 2025-12-29
**Keywords**: Python, 変数名, リファクタリング, NameError, cache_key, 未定義, name not defined
**Error**: "name 'cache_key' is not defined"
**影響範囲**: 検索ページのAI回答キャッシュ機能
**重要度**: 🔴 Critical

---

## 症状

検索実行時にエラーが発生し、AI回答が生成されない。

**期待動作**: AI回答が正常に生成される
**実際の動作**: `NameError: name 'cache_key' is not defined`

---

## 原因

変数名を `cache_key` から `session_cache_key` に変更したが、ファイル内の一部で古い変数名 `cache_key` がそのまま残っていた。

```python
# 変更した部分
session_cache_key = f"answer_{hash(query + str(selected_category))}"

# 変更し忘れた部分（エラーの原因）
cached_answer = st.session_state.get(cache_key, "")  # ← cache_key が未定義
```

**根本原因**:
- 変数名変更時に全ての使用箇所を確認しなかった
- 同一ファイル内の複数箇所で同じ変数を使用していた

---

## 対処

Grepで該当変数を検索し、すべての使用箇所を修正。

```bash
# 検索コマンド
grep -n "cache_key" pages/1_🔍_検索.py
```

```python
# 修正後
cached_answer = st.session_state.get(session_cache_key, "")
```

**ポイント**:
- `replace_all=True` オプションで一括置換可能
- 変更前にGrepで使用箇所を確認する

---

## 修正ファイル

- `pages/1_🔍_検索.py` (行342, 372)

---

## 予防策

1. 変数名変更時は必ずGrepで全使用箇所を確認
2. IDEの「すべての参照を検索」機能を活用
3. 変更後にテスト実行して動作確認

---

## 学んだこと

- 変数名のリファクタリングは一括置換で行う
- 置換後は必ず動作確認する
- 大きなファイルでは特に注意が必要
