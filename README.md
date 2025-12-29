# TikTok Creator Marketplace Crawler
> Công cụ tự động thu thập dữ liệu (Web Scraping) các nhà sáng tạo nội dung (Content Creators) từ TikTok Creator Marketplace sử dụng **Selenium** và **MongoDB**.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Selenium](https://img.shields.io/badge/Selenium-4.x-green)
![MongoDB](https://img.shields.io/badge/Database-MongoDB-leaf)

## Giới thiệu

Dự án này được thiết kế để tự động hóa việc thu thập dữ liệu hồ sơ KOLs/KOCs tại thị trường Việt Nam (hoặc quốc tế) phục vụ cho mục đích phân tích dữ liệu (Data Analysis) và Influencer Marketing.

Hệ thống có khả năng:
- Tự động đăng nhập và duy trì phiên làm việc qua Firefox Profile.
- Vượt qua cơ chế Lazy Loading (cuộn trang vô hạn).
- Chống chặn (Anti-ban) thông qua hành vi giả lập người dùng.
- Lưu trữ dữ liệu phi cấu trúc vào MongoDB.
- Tải và lưu trữ ảnh đại diện (Avatar) của Creator.

## Cấu trúc dự án

```text
tiktok-crawler-project/             
├── config/
│   ├── settings.py              # Cấu hình đường dẫn, database, selenium
├── src/
│   ├── bot_engine.py            # Logic chính của Selenium Bot
│   ├── db_connector.py          # Module kết nối MongoDB
│   ├── avatar_encoder.py        # Lấy dữ liệu hình ảnh
│   └── cleaner.py               # Module làm sạch dữ liệu và tải ảnh
├── main.py                      # File khởi chạy chương trình
├── Analysis.ipynb               # File phân tích dữ liệu sau khi thu thập
├── requirements.txt             # Danh sách thư viện cần thiết
└── README.md                    # Tài liệu hướng dẫn