# YARTIX-TICKETING-TEST

Flask + Google Sheets 的活動報名系統，提供手機友善的線上報名頁、API 後端與 Render 部署設定。

## 功能

- 首頁顯示活動資訊與報名開放倒數
- 依報名人數動態生成多人報名表單
- 前後端皆有欄位驗證，降低送單錯誤
- 報名資料寫入 Google Sheets
- 報名完成後顯示摘要與 LINE 群組連結
- 響應式介面，適配手機與桌機

## 技術架構

- 後端：Flask
- 前端：原生 JavaScript + Bootstrap 5
- 樣式：獨立 CSS 檔案
- 資料儲存：Google Sheets（gspread）
- 部署：Render + Gunicorn

## 專案結構

- `app.py`：Flask API 與報名邏輯
- `templates/index.html`：前端容器頁
- `static/js/app.js`：前端互動與表單生成
- `static/css/app.css`：手機優先的版面樣式
- `render.yaml`：Render 部署設定
- `Procfile`：Gunicorn 啟動設定

## 本機開發

1. 建立並啟動虛擬環境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. 安裝依賴

```powershell
pip install -r requirements.txt
```

3. 設定 Google Sheets 憑證

本機可直接使用專案內的 `credentials.json`，或設定環境變數：

```powershell
$env:GOOGLE_CREDENTIALS_PATH="C:\path\to\credentials.json"
$env:GOOGLE_SHEET_NAME="主售票系統  2026 春映洄瀾，拾光"
```

4. 啟動服務

```powershell
python app.py
```

## Render 部署

1. 將此專案推上 GitHub。
2. 在 Render 建立新的 Web Service，連結你的 GitHub repository。
3. 使用以下設定：
	- Build Command：`pip install -r requirements.txt`
	- Start Command：`gunicorn app:app`
4. 在環境變數中設定：
	- `GOOGLE_SHEET_NAME`
	- `GOOGLE_CREDENTIALS_JSON`
5. 將 Google 服務帳號 JSON 內容完整貼到 `GOOGLE_CREDENTIALS_JSON`。

`render.yaml` 已提供可直接匯入 Render 的基礎設定。

## 安全提醒

- 不要把 `credentials.json` 上傳到公開倉庫。
- 如需公開專案，請確認 Google Sheets 服務帳號權限只開給必要試算表。
- 建議為 Render 環境使用獨立憑證，不要共用本機開發憑證。

## 目前狀態

- 前後端已分離
- 已加入手機版 RWD
- 已可用 Render 部署
- 已避免把 Google 憑證納入 Git 追蹤