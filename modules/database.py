"""
ChromaDB操作モジュール
ベクトル検索・データ管理
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
import chromadb
from chromadb.config import Settings

from config.settings import (
    CHROMA_COLLECTION_NAME,
    PRACTICES_JSON,
    SEARCH_TOP_K,
    DATA_DIR,
    logger
)
from .embedding import get_embedding


class ChromaManager:
    """ChromaDBマネージャー"""

    def __init__(self, persistent: bool = False):
        """
        Args:
            persistent: True=ファイル永続化, False=メモリ上
        """
        logger.debug(f"[ChromaDB] 初期化開始 (persistent={persistent})")

        if persistent:
            self.client = chromadb.PersistentClient(
                path=str(DATA_DIR / "chroma_db")
            )
        else:
            self.client = chromadb.Client()

        # コレクション取得または作成
        self.collection = self.client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}  # コサイン類似度
        )

        logger.debug(f"[ChromaDB] 初期化完了 (既存データ: {self.collection.count()}件)")

    def load_from_json(self, json_path: Path = None) -> int:
        """
        JSONファイルからデータを読み込んでChromaDBに登録（バッチ処理対応）

        Returns:
            登録件数
        """
        from .embedding import get_embeddings_batch
        
        json_path = json_path or PRACTICES_JSON
        logger.debug(f"[ChromaDB] JSONから読み込み: {json_path}")

        if not json_path.exists():
            logger.warning(f"[ChromaDB] JSONファイルが存在しません: {json_path}")
            return 0

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        practices = data.get("practices", [])
        if not practices:
            logger.debug("[ChromaDB] 登録データなし")
            return 0
            
        logger.info(f"[ChromaDB] {len(practices)}件のデータを一括登録開始")

        # 既存データをクリア
        if self.collection.count() > 0:
            logger.debug("[ChromaDB] 既存データをクリア")
            all_ids = self.collection.get()["ids"]
            if all_ids:
                self.collection.delete(ids=all_ids)

        # 一括処理用にデータ準備
        ids = []
        documents = []
        metadatas = []
        
        for practice in practices:
            practice_id = practice.get("id") or str(uuid.uuid4())
            search_text = self._create_search_text(practice)
            
            metadata = {
                "title": practice.get("title", ""),
                "category": practice.get("category", "other"),
                "content_type": practice.get("content_type", "code"),
                "tags": ",".join(practice.get("tags", [])),
                "created_at": practice.get("created_at", ""),
                "updated_at": practice.get("updated_at", ""),
                "has_svg": bool(practice.get("generated_svg")),
                "has_html": bool(practice.get("generated_html")),
                "has_image": bool(practice.get("image_path"))
            }
            
            ids.append(practice_id)
            documents.append(search_text)
            metadatas.append(metadata)
        
        # 一括Embedding取得（1回のAPI呼び出し）
        logger.info(f"[ChromaDB] Embedding一括取得中... ({len(documents)}件)")
        embeddings = get_embeddings_batch(documents)
        
        # ChromaDBに一括登録
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )

        logger.info(f"[ChromaDB] 全{len(practices)}件の一括登録完了")
        return len(practices)

    def add_practice(self, practice: dict) -> str:
        """
        ベストプラクティスを追加

        Args:
            practice: practices.jsonの1エントリ

        Returns:
            登録したID
        """
        practice_id = practice.get("id") or str(uuid.uuid4())

        # 検索用テキスト生成（タイトル + 説明 + タグ）
        search_text = self._create_search_text(practice)

        # ベクトル化
        embedding = get_embedding(search_text)

        # メタデータ
        metadata = {
            "title": practice.get("title", ""),
            "category": practice.get("category", "other"),
            "content_type": practice.get("content_type", "code"),
            "tags": ",".join(practice.get("tags", [])),
            "created_at": practice.get("created_at", ""),
            "updated_at": practice.get("updated_at", ""),
            "has_svg": bool(practice.get("generated_svg")),
            "has_html": bool(practice.get("generated_html")),
            "has_image": bool(practice.get("image_path"))
        }

        # ChromaDBに追加
        self.collection.add(
            ids=[practice_id],
            embeddings=[embedding],
            metadatas=[metadata],
            documents=[search_text]
        )

        logger.debug(f"[ChromaDB] 追加: {practice_id} - {practice.get('title', '')[:30]}")
        return practice_id

    def _create_search_text(self, practice: dict) -> str:
        """検索用テキスト生成"""
        parts = [
            practice.get("title", ""),
            practice.get("description", ""),
            " ".join(practice.get("tags", []))
        ]
        return " ".join(filter(None, parts))

    def search(
        self,
        query: str,
        category: str = None,
        top_k: int = None
    ) -> list[dict]:
        """
        類似検索

        Args:
            query: 検索クエリ
            category: カテゴリフィルタ（None=全て）
            top_k: 取得件数

        Returns:
            検索結果リスト
        """
        top_k = top_k or SEARCH_TOP_K
        logger.debug(f"[ChromaDB] 検索: '{query}' (category={category}, top_k={top_k})")

        # クエリをベクトル化
        query_embedding = get_embedding(query)

        # フィルタ条件
        where = None
        if category and category != "all":
            where = {"category": category}

        # 検索実行
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["metadatas", "documents", "distances"]
        )

        # 結果整形
        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, id_ in enumerate(results["ids"][0]):
                result = {
                    "id": id_,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "document": results["documents"][0][i] if results["documents"] else "",
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                    "score": 1 - results["distances"][0][i] if results["distances"] else 1
                }
                search_results.append(result)
                logger.debug(f"[ChromaDB] 結果{i+1}: score={result['score']:.3f} - {result['metadata'].get('title', '')[:30]}")

        logger.debug(f"[ChromaDB] 検索完了: {len(search_results)}件")
        return search_results

    def search_visuals(
        self,
        query: str,
        min_score: float = 0.4,
        top_k: int = 3
    ) -> list[dict]:
        """
        図解（SVG/HTML）を持つデータのみ検索

        Args:
            query: 検索クエリ
            min_score: 最低類似度スコア（0.0-1.0）
            top_k: 取得件数

        Returns:
            検索結果リスト（has_svg=True または has_html=True のみ）
        """
        logger.debug(f"[ChromaDB] 図解検索: '{query}' (min_score={min_score})")

        query_embedding = get_embedding(query)

        # SVGまたはHTMLを持つデータのみ検索
        # ChromaDBの$orフィルタを使用
        where = {
            "$or": [
                {"has_svg": True},
                {"has_html": True}
            ]
        }

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["metadatas", "documents", "distances"]
        )

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, id_ in enumerate(results["ids"][0]):
                score = 1 - results["distances"][0][i] if results["distances"] else 1
                # 最低スコア以上のみ追加
                if score >= min_score:
                    result = {
                        "id": id_,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "document": results["documents"][0][i] if results["documents"] else "",
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                        "score": score
                    }
                    search_results.append(result)
                    logger.debug(f"[ChromaDB] 図解結果: score={score:.3f} - {result['metadata'].get('title', '')[:30]}")

        logger.info(f"[ChromaDB] 図解検索完了: {len(search_results)}件 (min_score={min_score})")
        return search_results

    def search_images(
        self,
        query: str,
        min_score: float = 0.4,
        top_k: int = 3
    ) -> list[dict]:
        """
        画像を持つデータのみ検索

        Args:
            query: 検索クエリ
            min_score: 最低類似度スコア（0.0-1.0）
            top_k: 取得件数

        Returns:
            検索結果リスト（has_image=True のみ）
        """
        logger.debug(f"[ChromaDB] 画像検索: '{query}' (min_score={min_score})")

        query_embedding = get_embedding(query)

        # 画像を持つデータのみ検索
        where = {"has_image": True}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["metadatas", "documents", "distances"]
        )

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, id_ in enumerate(results["ids"][0]):
                score = 1 - results["distances"][0][i] if results["distances"] else 1
                if score >= min_score:
                    result = {
                        "id": id_,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "document": results["documents"][0][i] if results["documents"] else "",
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                        "score": score
                    }
                    search_results.append(result)
                    logger.debug(f"[ChromaDB] 画像結果: score={score:.3f} - {result['metadata'].get('title', '')[:30]}")

        logger.info(f"[ChromaDB] 画像検索完了: {len(search_results)}件 (min_score={min_score})")
        return search_results

    def delete(self, practice_id: str) -> bool:
        """
        データ削除

        Args:
            practice_id: 削除対象ID

        Returns:
            成功=True
        """
        logger.debug(f"[ChromaDB] 削除: {practice_id}")
        try:
            self.collection.delete(ids=[practice_id])
            logger.debug(f"[ChromaDB] 削除完了: {practice_id}")
            return True
        except Exception as e:
            logger.error(f"[ChromaDB] 削除エラー: {e}")
            return False

    def get_count(self) -> int:
        """登録件数取得"""
        return self.collection.count()


if __name__ == "__main__":
    # テスト実行
    print("=== ChromaDB テスト ===")

    manager = ChromaManager(persistent=False)
    print(f"初期データ数: {manager.get_count()}")

    # テストデータ追加
    test_practice = {
        "id": "test-001",
        "title": "Flexboxカードレイアウト",
        "description": "カードを横並びで均等に配置する方法",
        "category": "html_css",
        "content_type": "code",
        "tags": ["flexbox", "card", "layout"]
    }

    manager.add_practice(test_practice)
    print(f"追加後データ数: {manager.get_count()}")

    # 検索テスト
    results = manager.search("カードを横に並べたい")
    print(f"検索結果: {len(results)}件")
    for r in results:
        print(f"  - {r['metadata']['title']} (score: {r['score']:.3f})")
