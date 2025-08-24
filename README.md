# 🎯 Website Phân tích & Thống kê Xổ số Miền Bắc

Dự án xây dựng một website quản lý, thống kê và phân tích kết quả xổ số miền Bắc (SXMB).  
Hệ thống hỗ trợ người dùng tra cứu kết quả, phân tích tần suất, chạm, cầu lô, cũng như quản lý tài khoản, nạp/rút tiền và chức năng admin.

---

## 📂 Cấu trúc thư mục

```bash
.
├── app/
│   ├── static/              # File tĩnh (CSS, hình ảnh, JS)
│   │   ├── banks/           # Dữ liệu ngân hàng
│   │   ├── img/             # Hình ảnh
│   │   └── *.css            # File giao diện
│   │
│   ├── templates/           # HTML templates (giao diện)
│   │   ├── index.html       # Trang chủ
│   │   ├── dang_nhap.html   # Đăng nhập
│   │   ├── dang_ky.html     # Đăng ký
│   │   ├── phan_tich.html   # Phân tích SXMB
│   │   ├── thong_ke.html    # Thống kê
│   │   └── ...              # Các trang khác (bank, admin, nạp/rút tiền, ...)
│   │
│   ├── utils/               # Xử lý dữ liệu, crawl, phân tích
│   │   ├── crawl.py         # Crawl dữ liệu kết quả SXMB
│   │   ├── du_lieu.py       # Lấy dữ liệu của ngày chỉ định
│   │   ├── phan_tich.py     # Hàm phân tích thống kê
│   │   └── __init__.py
│   │
│   ├── models/              # Kết nối và định nghĩa database
│   │   ├── database.py      # Kết nối DB (MongoDB)
│   │   └── __init__.py
│   │
│   └── routes/              # Flask routes (Controller)
│       ├── admin.py         # Quản lý admin
│       ├── dang_nhap.py     # Đăng nhập/Đăng ký
│       ├── du_doan.py       # Dự đoán SXMB
│       ├── ghi_lo.py        # Quản lý ghi lô
│       ├── index.py         # Route trang chủ
│       ├── nap_rut_ls.py    # Nạp/rút tiền & lịch sử
│       ├── tk_pt.py         # Router thống kê & phân tích
│       └── __init__.py
│
├── run.py                   # File chạy chính của ứng dụng
├── bank.py                  # Xử lý nghiệp vụ ngân hàng
├── hi.py                    # File test tạo tài khoản admin
├── requirements.txt         # Danh sách thư viện cần cài
├── .env                     # Biến môi trường (DB_URL, SECRET_KEY, ...)
└── README.md                # Tài liệu hướng dẫn



## 🎥 Demo Video

(https://youtu.be/E4EE04ItZ1U)
