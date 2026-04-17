# Yartix-main

## 本機啟動
1. 建立 Python 3.11 環境並安裝依賴：
   ```bash
   pip install -r requirements.txt
   ```
2. 複製環境變數範本：
   ```bash
   copy .env.example .env
   ```
3. 填入 `.env` 的 SMTP 與 Google Sheet 設定。
4. 啟動：
   ```bash
   python app.py
   ```

## 唯一啟動守則（避免多進程讀到舊設定）
- 請只啟動一個 `python app.py`。
- 程式啟動時會寫入 `.app.pid`，若偵測到舊進程仍在執行，會直接拒絕啟動。

## .env 與敏感資料
- `.env` 僅限本機使用，不可加入版控。
- `credentials.json` 僅限本機，Render 建議使用 `GOOGLE_CREDENTIALS_JSON`。
- SMTP App Password 請使用 Gmail 16 碼密碼，且上線前先重新產生（rotate）。

## 重送機制
- 當付款 Email 寄送失敗，會寫入 `email_retry_queue.jsonl`。
- 呼叫 API 重送：
  ```bash
  curl -X POST http://127.0.0.1:8080/api/retry-email-queue
  ```

## API Smoke Tests
- 健康檢查與報名：
  ```bash
  python test_registration_bot.py --base-url http://127.0.0.1:8080 --rounds 1 --min-participants 1 --max-participants 1
  ```

## 單元測試
```bash
pytest -q
```

## 常見錯誤排除
- `E_SMTP_CONFIG`：SMTP 參數缺漏、仍是範例密碼，或密碼含非 ASCII。
- `E_SHEET_UNAVAILABLE`：Google Sheet 憑證或連線異常。
- `E_SHEET_WRITE`：Sheet 寫入失敗（權限/欄位異常）。
- `E_VALIDATION`：使用者輸入格式不符合規則。
