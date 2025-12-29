import os
import requests
from config.setting import IMAGE_FOLDER

class DataCleaner:
    @staticmethod
    def download_avatar(url, creator_id):
        """
        Tải ảnh từ URL -> Lưu vào folder assets/avatars
        """
        if not url:
            return ""
        
        try:
            safe_id = "".join([c for c in creator_id if c.isalnum() or c in ('-','_','.')])
            filename = f"{safe_id}.jpg"
            file_path = os.path.join(IMAGE_FOLDER, filename)
            
            # Nếu file đã tồn tại và > 0KB thì bỏ qua
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                return file_path

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.tiktok.com/",
            }

            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                return file_path
            return ""
        except Exception as e:
            # print(f"Lỗi tải ảnh {creator_id}: {e}")
            return ""

    @staticmethod
    def clean_text(text):
        """Hàm làm sạch text cơ bản nếu cần"""
        return text.strip() if text else "N/A"