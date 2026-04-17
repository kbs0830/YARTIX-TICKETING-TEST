# Yartix 主專案說明

本專案已完成整理為前後端分離結構，並清除測試與非正式執行檔案，保留正式網站運作所需內容。

## 目錄結構

```text
Yartix-main/
├─ backend/                 # 後端 Flask 與商業邏輯
│  ├─ app.py                # Flask API/路由入口（WSGI: backend.app:app）
│  ├─ config.py             # 設定載入與驗證
│  ├─ registration_service.py
│  ├─ sheet_service.py
│  ├─ email_service.py
│  ├─ models.py
│  ├─ errors.py
│  ├─ logging_utils.py
│  └─ startup_guard.py
├─ frontend/
│  ├─ templates/
│  │  └─ index.html         # 前端頁面模板
│  └─ static/               # CSS/JS/圖片/公告內容
├─ run.py                   # 本機啟動入口
├─ MAIN.md                  # 快速入口文件
├─ Procfile                 # 平台啟動設定（Gunicorn）
├─ render.yaml              # Render 部署設定
├─ requirements.txt
├─ .env.example
└─ README.md
```

## 本機啟動（不使用虛擬環境）

1. 安裝依賴

```bash
pip install -r requirements.txt
```

2. 建立環境變數檔

```bash
copy .env.example .env
```

3. 編輯 `.env`，填入 SMTP 與 Google Sheet 參數。

4. 啟動服務

```bash
python run.py
```

5. 開啟 `http://127.0.0.1:8080`

## 部署與標準規範

- WSGI 啟動點：`backend.app:app`
- Render 啟動命令：`gunicorn backend.app:app`
- 前後端分離：後端位於 `backend/`，前端資源位於 `frontend/`
- 設定與敏感資訊：`.env`、`credentials.json` 不進版控

## API

- `GET /api/bootstrap`：載入活動設定與剩餘資訊
- `POST /api/register`：送出報名
- `POST /api/retry-email-queue`：重送失敗付款信

## 錯誤碼

- `E_INVALID_PAYLOAD`
- `E_VALIDATION`
- `E_SHEET_UNAVAILABLE`
- `E_SHEET_WRITE`
- `E_SHEET_SCHEMA`
- `E_SMTP_CONFIG`
- `E_SMTP_SEND`
- `E_PUSH_CONFIG`
- `E_PUSH_SEND`
