import os
import json
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config.settings import PRACTICES_JSON, PROJECT_ROOT, logger, GOOGLE_DRIVE_CREDENTIALS_PATH, GOOGLE_DRIVE_FOLDER_ID

# 定数
SCOPES = ['https://www.googleapis.com/auth/drive']
CREDENTIALS_PATH = Path(GOOGLE_DRIVE_CREDENTIALS_PATH)
DRIVE_FOLDER_NAME = "RAG_APP_DATA"
TARGET_FILE_NAME = "practices.json"

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

    def _find_file_in_drive(self):
        """フォルダ内のpractices.jsonを探す"""
        if not self.service or not self.folder_id:
            return None
        
        try:
            query = f"name='{TARGET_FILE_NAME}' and '{self.folder_id}' in parents and trashed=false"
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
            logger.error(f"[DriveManager] ファイル検索エラー: {e}")
            return None

    def download_practices(self) -> bool:
        """Driveからダウンロードしてローカルを上書き"""
        if not self.service:
            return False

        file_id = self._find_file_in_drive()
        if not file_id:
            logger.info("[DriveManager] Drive上にファイルなし。スキップします。")
            return False

        try:
            # supportsAllDrives=True を追加
            content = self.service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True
            ).execute()
            
            # 下書き保存（万が一の破損防止）しないで直接上書きでOK（今回はシンプルに）
            with open(PRACTICES_JSON, 'wb') as f:
                f.write(content)
            
            logger.info(f"[DriveManager] ダウンロード完了: {PRACTICES_JSON}")
            return True
            
        except Exception as e:
            logger.error(f"[DriveManager] ダウンロード失敗: {e}")
            return False

    def upload_practices(self) -> bool:
        """ローカルのpractices.jsonをDriveにアップロード（上書き）"""
        if not self.service or not self.folder_id:
            return False

        if not PRACTICES_JSON.exists():
            logger.warning("[DriveManager] アップロード対象のローカルファイルがありません")
            return False

        file_id = self._find_file_in_drive()
        
        try:
            media = MediaFileUpload(str(PRACTICES_JSON), mimetype='application/json', resumable=True)
            
            if file_id:
                # 更新 (update)
                # supportsAllDrives=True を追加
                self.service.files().update(
                    fileId=file_id,
                    media_body=media,
                    supportsAllDrives=True
                ).execute()
                logger.info(f"[DriveManager] アップロード完了（更新）: {file_id}")
            else:
                # 新規作成 (create)
                file_metadata = {
                    'name': TARGET_FILE_NAME,
                    'parents': [self.folder_id]
                }
                # supportsAllDrives=True を追加
                self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id',
                    supportsAllDrives=True
                ).execute()
                logger.info("[DriveManager] アップロード完了（新規作成）")
            
            return True

        except Exception as e:
            logger.error(f"[DriveManager] アップロード失敗: {e}")
            return False
