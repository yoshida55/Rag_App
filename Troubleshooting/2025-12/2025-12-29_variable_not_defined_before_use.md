# 変数未定義エラー: registration_mode

## Keywords
variable not defined, NameError, registration_mode, session_state, Streamlit, 変数未定義, セクション表示, checkbox

## Error
```
ERROR: [検索] AI回答生成エラー: name 'registration_mode' is not defined
```

## 症状
- 登録モードONにしても、セクション横のチェックボックスが表示されない
- ページ上部の緑バナーは表示される
- 参考データセクションのチェックボックスは表示される

## 原因
`registration_mode` 変数がセクション表示コード（284行目付近）で使用されているが、定義は640行目にあった。

コードの流れ:
1. AI回答生成 → セクション分割 → セクション表示（ここで `registration_mode` 使用）
2. 参考データ表示（ここで `registration_mode` 定義）

## 対処
セクション表示コードの前に `registration_mode` の定義を追加:

```python
# 279行目付近
# 🔹 登録モード取得（セクション表示で使用）
registration_mode = st.session_state.get("learning_registration_mode", False)

# 🔹 セクション別図解生成（AI回答直後に表示）
sections = split_answer_into_sections(answer_text or "")
```

## 修正ファイル
- `pages/1_🔍_検索.py` (279行目)

## 学んだこと
- 変数は使用箇所より前に定義する
- Streamlitのsession_stateは `.get()` で安全に取得
- ログに `ERROR` があれば必ず確認する
