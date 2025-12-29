# Streamlit で SVG が表示されない問題

**日付**: 2025-12-29
**Keywords**: Streamlit, SVG, st.markdown, unsafe_allow_html, st.components.v1.html, 図解, 表示されない
**Error**: SVGコードがHTMLとして描画されず、空白になる
**影響範囲**: 検索ページの図解表示機能
**重要度**: 🟡 Important

---

## 症状

AI生成したSVG図解が画面に表示されない。

**期待動作**: SVG図解が描画される
**実際の動作**: 空白のまま何も表示されない

---

## 原因

`st.markdown(svg_content, unsafe_allow_html=True)` でSVGを表示しようとしたが、Streamlitがセキュリティ上SVGをサニタイズしている可能性がある。

```python
# 問題のコード
st.markdown(f"""
<div style="background: #ffffff;">
    {svg_content}
</div>
""", unsafe_allow_html=True)
```

**根本原因**:
- Streamlitの`unsafe_allow_html`はすべてのHTMLを許可するわけではない
- SVGタグは一部サニタイズされる可能性がある

---

## 対処

`st.components.v1.html()` を使用してSVGを表示する。

```python
# 修正後のコード
svg_html = f"""
<html>
<body style="margin:0; padding:15px; background:#ffffff;">
    <div style="border: 1px solid #4caf50; border-radius: 8px; padding: 10px;">
        {svg_content}
    </div>
</body>
</html>
"""
st.components.v1.html(svg_html, height=450, scrolling=True)
```

**ポイント**:
- `st.components.v1.html()` はiframeとして描画するため、SVGがそのまま表示される
- heightを指定しないと表示されない場合がある
- scrolling=Trueで大きなSVGもスクロール可能

---

## 修正ファイル

- `pages/1_🔍_検索.py` (行170-180付近)

---

## 予防策

- StreamlitでSVG/複雑なHTMLを表示する場合は `st.components.v1.html()` を使う
- `st.markdown(unsafe_allow_html=True)` はシンプルなHTMLのみに使用

---

## 学んだこと

- Streamlitの`unsafe_allow_html`は万能ではない
- SVGやスクリプトを含むHTMLは `st.components.v1.html()` で表示する
