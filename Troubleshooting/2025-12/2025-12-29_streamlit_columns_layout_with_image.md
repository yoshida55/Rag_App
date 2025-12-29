# Streamlit で画像の横にボタンを配置できない

**日付**: 2025-12-29
**Keywords**: Streamlit, st.columns, レイアウト, 画像, ボタン, 横並び, UI, 配置
**Error**: なし（レイアウトが期待通りにならない）
**影響範囲**: 画像削除ボタンのUI
**重要度**: 🟢 Minor

---

## 症状

画像の右横に削除ボタンを配置したいが、ボタンが画像の下に表示される。

**期待動作**:
```
[   画像   ] [🗑]
```

**実際の動作**:
```
[   画像   ]
[🗑]
```

---

## 原因

`st.columns()` で画像とボタンを横並びにしても、画像が大きいため、ボタンが画像の下に押し出される。

```python
# 問題のコード
col_img, col_btn = st.columns([10, 1])
with col_img:
    st.image(image_path, use_container_width=True)  # 画像が大きい
with col_btn:
    st.button("🗑")  # ボタンが下に行く
```

**根本原因**:
- Streamlitのcolumnsは横幅を分割するが、高さは連動しない
- 画像が大きい場合、ボタンは画像の上部に配置されるが、目立たない

---

## 対処

画像の上（タイトル行）にボタンを配置する。

```python
# 修正後のコード
# タイトルと削除ボタンを横並び
col_title, col_del = st.columns([8, 1])
with col_title:
    st.caption(f"{title} (類似度: {score:.0%})")
with col_del:
    if st.button("🗑", key=f"del_{id}", help="削除"):
        # 削除処理

# 画像は別の行に表示
st.image(image_path, use_container_width=True)
```

**ポイント**:
- タイトル行はテキストなので高さが揃う
- ボタンが目立つ位置に配置される
- 画像は単独の行で表示

---

## 代替案

### 案1: 画像サイズを制限

```python
col_img, col_btn = st.columns([8, 1])
with col_img:
    st.image(image_path, width=400)  # 幅を制限
with col_btn:
    st.button("🗑")
```

### 案2: HTMLで直接レイアウト

```python
st.markdown(f"""
<div style="display: flex; align-items: flex-start;">
    <img src="{image_url}" style="flex: 1;">
    <button style="margin-left: 10px;">🗑</button>
</div>
""", unsafe_allow_html=True)
# ※ボタンのクリックイベントは動作しない
```

### 案3: オーバーレイ（CSS）

```python
st.markdown(f"""
<div style="position: relative;">
    <img src="{image_url}" style="width: 100%;">
    <span style="position: absolute; top: 10px; right: 10px;">🗑</span>
</div>
""", unsafe_allow_html=True)
# ※ボタンのクリックイベントは動作しない
```

---

## 修正ファイル

- `pages/1_🔍_検索.py` (画像表示部分のレイアウト)

---

## 予防策

1. Streamlitでは複雑なレイアウトは避ける
2. ボタンはテキストと同じ行に配置する
3. 画像は単独の行で表示するのがシンプル

---

## 学んだこと

- Streamlitのcolumnsは高さが揃わない
- 画像と他の要素の横並びは難しい
- シンプルなレイアウトを心がける
