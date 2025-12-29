# ChromaDB で特定属性を持つデータが検索結果に表示されない

**日付**: 2025-12-29
**Keywords**: ChromaDB, メタデータ, フィルタ, 検索, top_k, has_svg, has_image, 表示されない, 専用検索
**Error**: なし（データは存在するが検索結果に含まれない）
**影響範囲**: 保存済み図解・画像の自動表示
**重要度**: 🟡 Important

---

## 症状

保存済みの図解（SVG）や画像が検索結果に表示されない。データは存在するのに表示されない。

**期待動作**: 関連する保存済み図解・画像がAI回答の下に表示される
**実際の動作**: 何も表示されない

---

## 原因

通常の検索（top_k=5）では、SVGや画像を持つデータが上位5件に入らない場合がある。

```python
# 通常の検索
search_results = chroma_manager.search(query=query, top_k=5)

# 問題: SVG付きデータが6位以下だと取得されない
practices = [get_by_id(r["id"]) for r in search_results]
saved_svgs = [p for p in practices if p.get("generated_svg")]
# → 空になる可能性
```

**根本原因**:
- 検索結果のTOP5に特定属性（SVG/画像）を持つデータが含まれない
- フィルタリングを事後に行っているため、該当データが取得されない

---

## 対処

メタデータにフラグを追加し、専用の検索メソッドを作成。

### 1. メタデータにフラグ追加

```python
# database.py - add_practice()
metadata = {
    "title": practice.get("title", ""),
    "category": practice.get("category", "other"),
    "has_svg": bool(practice.get("generated_svg")),
    "has_html": bool(practice.get("generated_html")),
    "has_image": bool(practice.get("image_path"))
}
```

### 2. 専用検索メソッド作成

```python
# database.py
def search_visuals(self, query: str, min_score: float = 0.65, top_k: int = 3):
    """図解（SVG/HTML）を持つデータのみ検索"""
    where = {
        "$or": [
            {"has_svg": True},
            {"has_html": True}
        ]
    }
    results = self.collection.query(
        query_embeddings=[get_embedding(query)],
        n_results=top_k,
        where=where,
        include=["metadatas", "documents", "distances"]
    )
    # ...

def search_images(self, query: str, min_score: float = 0.65, top_k: int = 3):
    """画像を持つデータのみ検索"""
    where = {"has_image": True}
    # ...
```

### 3. 検索ページで使用

```python
# 図解専用検索
visual_results = chroma_manager.search_visuals(query=query, min_score=0.65)

# 画像専用検索
image_results = chroma_manager.search_images(query=query, min_score=0.65)
```

---

## 修正ファイル

- `modules/database.py` (メタデータ追加、search_visuals, search_images メソッド追加)
- `pages/1_🔍_検索.py` (専用検索メソッドの呼び出し)

---

## 予防策

1. 特定属性でフィルタリングが必要な場合は、メタデータにフラグを追加
2. 事後フィルタリングではなく、ChromaDBのwhereフィルタを使用
3. 複数の検索条件がある場合は専用メソッドを作成

---

## ChromaDB フィルタの書き方

```python
# 単一条件
where = {"has_svg": True}

# OR条件
where = {"$or": [{"has_svg": True}, {"has_html": True}]}

# AND条件
where = {"$and": [{"category": "html_css"}, {"has_svg": True}]}
```

---

## 学んだこと

- ChromaDBのメタデータフィルタは検索時に適用される
- 事後フィルタリングよりも効率的で確実
- 特定属性を持つデータの検索は専用メソッドで行う
