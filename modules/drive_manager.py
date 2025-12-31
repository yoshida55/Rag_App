import os
import json
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config.settings import PRACTICES_JSON, ANSWER_CACHE_JSON, PROJECT_ROOT, logger, GOOGLE_DRIVE_CREDENTIALS_PATH, GOOGLE_DRIVE_FOLDER_ID

# 定数
SCOPES = ['https://www.googleapis.com/auth/drive']
CREDENTIALS_PATH = Path(GOOGLE_DRIVE_CREDENTIALS_PATH)
DRIVE_FOLDER_NAME = "RAG_APP_DATA"
TARGET_FILE_NAME = "practices.json"
CACHE_FILE_NAME = "answer_cache.json"

class DriveManager:
    """Google Driveとのデータ同期を管理するクラス"""

    def __init__(self):
        self.service = None
        self.folder_id = GOOGLE_DRIVE_FOLDER_ID  # 設定からIDを読み込む
        self._authenticate()

    def _authenticate(self):
        """Google Drive APIの認証"""
        creds = None

        # 1. ローカルファイルの確認
        if CREDENTIALS_PATH.exists():
            try:
                creds = Credentials.from_service_account_file(
                    str(CREDENTIALS_PATH), scopes=SCOPES
                )
                logger.info("[DriveManager] 認証成功 (Local File)")
            except Exception as e:
                logger.error(f"[DriveManager] ファイル認証エラー: {e}")

        # 2. Streamlit Cloud (st.secrets) の確認
        if not creds:
            try:
                import streamlit as st
                # secrets.toml で [google_credentials] セクションに JSONの中身を展開して記述した場合
                if hasattr(st, "secrets") and "google_credentials" in st.secrets:
                    # st.secretsのプロキシオブジェクトをdictに変換
                    creds_info = dict(st.secrets["google_credentials"])
                    creds = Credentials.from_service_account_info(
                        creds_info, scopes=SCOPES
                    )
                    logger.info("[DriveManager] 認証成功 (Streamlit Secrets)")
            except Exception as e:
                logger.error(f"[DriveManager] Secrets認証エラー: {e}")

        if not creds:
            logger.warning(f"[DriveManager] 認証失敗: 認証ファイルも見つからず、st.secretsにも設定がありません")
            return

        try:
            self.service = build('drive', 'v3', credentials=creds)
            
            # フォルダIDが設定になければ、検索・作成
            if not self.folder_id:
                self.folder_id = self._get_or_create_folder()
            else:
                logger.debug(f"[DriveManager] 設定済みフォルダIDを使用: {self.folder_id}")
            
        except Exception as e:
            logger.error(f"[DriveManager] サービス構築エラー: {e}")

    def _get_or_create_folder(self):
        """データ保存用フォルダのIDを取得、なければ作成"""
        if not self.service:
            return None

        try:
            # フォルダ検索
            query = f"mimeType='application/vnd.google-apps.folder' and name='{DRIVE_FOLDER_NAME}' and trashed=false"
            # supportsAllDrives=True を追加
            results = self.service.files().list(
                q=query, 
                fields="files(id, name)", 
                supportsAllDrives=True, 
                includeItemsFromAllDrives=True
            ).execute()
            items = results.get('files', [])

            if items:
                folder_id = items[0]['id']
                logger.debug(f"[DriveManager] フォルダ発見: {folder_id}")
                return folder_id
            
            # 作成
            file_metadata = {
                'name': DRIVE_FOLDER_NAME,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            # supportsAllDrives=True を追加
            folder = self.service.files().create(
                body=file_metadata, 
                fields='id',
                supportsAllDrives=True
            ).execute()
            logger.info(f"[DriveManager] フォルダ作成: {folder.get('id')}")
            return folder.get('id')

        except Exception as e:
            logger.error(f"[DriveManager] フォルダ取得エラー: {e}")
            return None

    def _find_file_in_drive(self, filename: str):
        """指定されたファイル名を探す"""
        if not self.service or not self.folder_id:
            return None
        
        try:
            query = f"name='{filename}' and '{self.folder_id}' in parents and trashed=false"
            # supportsAllDrives=True を追加
            results = self.service.files().list(
                q=query, 
                fields="files(id, name)",
                supportsAllDrives=True, 
                includeItemsFromAllDrives=True
            ).execute()
            items = results.get('files', [])
            
            if items:
                return items[0]['id']
            return None
        except Exception as e:
            logger.error(f"[DriveManager] ファイル検索エラー ({filename}): {e}")
            return None

    def _download_file(self, filename: str, local_path: Path) -> bool:
        """汎用ダウンロード処理"""
        if not self.service:
            return False

        file_id = self._find_file_in_drive(filename)
        if not file_id:
            logger.info(f"[DriveManager] Drive上にファイルなし: {filename}")
            return False

        try:
            # supportsAllDrives=True を追加
            content = self.service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True
            ).execute()
            
            with open(local_path, 'wb') as f:
                f.write(content)
            
            logger.info(f"[DriveManager] ダウンロード完了: {local_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"[DriveManager] ダウンロード失敗 ({filename}): {e}")
            return False

    def _upload_file(self, filename: str, local_path: Path) -> bool:
        """汎用アップロード処理"""
        if not self.service or not self.folder_id:
            return False

        if not local_path.exists():
            logger.warning(f"[DriveManager] アップロード対象のローカルファイルがありません: {local_path}")
            return False

        file_id = self._find_file_in_drive(filename)
        
        try:
            media = MediaFileUpload(str(local_path), mimetype='application/json', resumable=True)
            
            if file_id:
                # 更新 (update)
                self.service.files().update(
                    fileId=file_id,
                    media_body=media,
                    supportsAllDrives=True
                ).execute()
                logger.info(f"[DriveManager] アップロード完了（更新）: {filename}")
            else:
                # 新規作成 (create)
                file_metadata = {
                    'name': filename,
                    'parents': [self.folder_id]
                }
                self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id',
                    supportsAllDrives=True
                ).execute()
                logger.info(f"[DriveManager] アップロード完了（新規作成）: {filename}")
            
            return True

        except Exception as e:
            logger.error(f"[DriveManager] アップロード失敗 ({filename}): {e}")
            return False

    def download_practices(self) -> bool:
        """practices.json ダウンロード"""
        return self._download_file(TARGET_FILE_NAME, PRACTICES_JSON)

    def upload_practices(self) -> bool:
        """practices.json アップロード"""
        return self._upload_file(TARGET_FILE_NAME, PRACTICES_JSON)

    def download_cache(self) -> bool:
        """answer_cache.json ダウンロード"""
        return self._download_file(CACHE_FILE_NAME, ANSWER_CACHE_JSON)

    def upload_cache(self) -> bool:
        """answer_cache.json アップロード"""
        return self._upload_file(CACHE_FILE_NAME, ANSWER_CACHE_JSON)
