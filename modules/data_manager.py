"""
データ管理モジュール
practices.json の読み書き
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import PRACTICES_JSON, DATA_DIR, logger
from modules.drive_manager import DriveManager


class DataManager:
    """practices.json 管理クラス"""

    def __init__(self, json_path: Path = None):
        self.json_path = json_path or PRACTICES_JSON
        
        # Drive同期マネージャー
        self.drive_manager = DriveManager()
        
        # 起動時にDriveから最新データを取得（同期）
        # もしDriveにファイルがなければ（初回など）、ローカルのデータをアップロードしてあげる
        if not self.drive_manager.download_practices():
            logger.info("[DataManager] Driveにデータがないため、初回アップロードを実行します")
            self.drive_manager.upload_practices()
        
        self._ensure_file_exists()
        logger.debug(f"[DataManager] 初期化: {self.json_path}")

    def _ensure_file_exists(self):
        """ファイルが存在しない場合は空のデータで作成"""
        if not self.json_path.exists():
            self.json_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_data({"practices": []})
            logger.debug(f"[DataManager] 新規ファイル作成: {self.json_path}")

    def _load_data(self) -> dict:
        """データ読み込み"""
        with open(self.json_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_data(self, data: dict):
        """データ保存"""
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Driveへバックアップ（非同期でやるとUI止まらないが、まずは同期で確実に）
        self.drive_manager.upload_practices()

    def get_all(self) -> list[dict]:
        """全データ取得"""
        data = self._load_data()
        practices = data.get("practices", [])
        logger.debug(f"[DataManager] 全データ取得: {len(practices)}件")
        return practices

    def get_by_id(self, practice_id: str) -> Optional[dict]:
        """IDでデータ取得"""
        practices = self.get_all()
        for p in practices:
            if p.get("id") == practice_id:
                logger.debug(f"[DataManager] ID検索成功: {practice_id}")
                return p
        logger.debug(f"[DataManager] ID検索失敗: {practice_id}")
        return None

    def add(self, practice: dict) -> str:
        """
        データ追加

        Args:
            practice: 追加するデータ（id省略可）

        Returns:
            追加したデータのID
        """
        data = self._load_data()
        practices = data.get("practices", [])

        # IDがなければ生成
        if not practice.get("id"):
            practice["id"] = str(uuid.uuid4())

        # タイムスタンプ
        now = datetime.now().isoformat()
        practice["created_at"] = practice.get("created_at") or now
        practice["updated_at"] = now

        practices.append(practice)
        data["practices"] = practices
        self._save_data(data)

        logger.debug(f"[DataManager] 追加: {practice['id']} - {practice.get('title', '')[:30]}")
        return practice["id"]

    def update(self, practice_id: str, updates: dict) -> bool:
        """
        データ更新

        Args:
            practice_id: 更新対象ID
            updates: 更新内容

        Returns:
            成功=True
        """
        data = self._load_data()
        practices = data.get("practices", [])

        for i, p in enumerate(practices):
            if p.get("id") == practice_id:
                # 更新
                practices[i].update(updates)
                practices[i]["updated_at"] = datetime.now().isoformat()
                data["practices"] = practices
                self._save_data(data)
                logger.debug(f"[DataManager] 更新: {practice_id}")
                return True

        logger.warning(f"[DataManager] 更新対象なし: {practice_id}")
        return False

    def delete(self, practice_id: str) -> bool:
        """
        データ削除

        Args:
            practice_id: 削除対象ID

        Returns:
            成功=True
        """
        data = self._load_data()
        practices = data.get("practices", [])

        original_count = len(practices)
        practices = [p for p in practices if p.get("id") != practice_id]

        if len(practices) < original_count:
            data["practices"] = practices
            self._save_data(data)
            logger.debug(f"[DataManager] 削除: {practice_id}")
            return True

        logger.warning(f"[DataManager] 削除対象なし: {practice_id}")
        return False

    def get_by_category(self, category: str) -> list[dict]:
        """カテゴリでフィルタ"""
        practices = self.get_all()
        filtered = [p for p in practices if p.get("category") == category]
        logger.debug(f"[DataManager] カテゴリ検索: {category} -> {len(filtered)}件")
        return filtered

    def search_by_text(self, keyword: str) -> list[dict]:
        """テキスト検索（タイトル・説明・タグ）"""
        practices = self.get_all()
        keyword_lower = keyword.lower()

        results = []
        for p in practices:
            searchable = " ".join([
                p.get("title", ""),
                p.get("description", ""),
                " ".join(p.get("tags", []))
            ]).lower()

            if keyword_lower in searchable:
                results.append(p)

        logger.debug(f"[DataManager] テキスト検索: '{keyword}' -> {len(results)}件")
        return results


if __name__ == "__main__":
    # テスト実行
    print("=== DataManager テスト ===")

    dm = DataManager()
    print(f"現在のデータ数: {len(dm.get_all())}件")

    # テストデータ追加
    test_id = dm.add({
        "title": "テストデータ",
        "category": "html_css",
        "content_type": "code",
        "description": "テスト用のデータです",
        "tags": ["test", "sample"]
    })
    print(f"追加したID: {test_id}")

    # 取得
    data = dm.get_by_id(test_id)
    print(f"取得したデータ: {data['title']}")

    # 削除
    dm.delete(test_id)
    print(f"削除後のデータ数: {len(dm.get_all())}件")
