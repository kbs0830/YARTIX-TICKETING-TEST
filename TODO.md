# Yartix 專案優化 TODO（掃描版）

更新時間：2026-04-17
範圍：整個專案資料夾

## P0 立即處理（穩定性/資安）
- [ ] 移除敏感資訊外露風險：重新產生 SMTP App Password，確認 `.env` 只在本機使用且不進版控。
- [ ] 新增「唯一啟動守則」：避免同時啟動多個 `app.py`（曾發生多進程導致讀到舊設定）。
- [ ] 補上啟動檢查：啟動時輸出關鍵設定檢查（SMTP、Google Sheet）但不印出密碼內容。
- [ ] 付款信與推送失敗改用結構化 log（含 error code / request id）。
- [ ] 將 Python 版本調整至穩定版本（建議 3.11 或 3.12），避免 3.14 相依風險。

## P1 核心品質（可維護/可擴充）
- [ ] 將 `app.py` 模組化：`email_service.py`、`sheet_service.py`、`registration_service.py`。
- [ ] 補齊型別與資料模型（建議 dataclass 或 pydantic）統一 participant 欄位。
- [ ] 統一設定管理：所有環境變數集中於 `config` 區塊並加預設/驗證。
- [ ] 加上錯誤碼回傳（例如 `E_SMTP_CONFIG`、`E_SHEET_WRITE`）以便前端顯示與排錯。
- [ ] 清理未使用常數/設定（例如目前未實際使用項目）。

## P1 效能與一致性
- [ ] 優化 `remaining_seats()`：避免每次都 `get_all_records()` 全表讀取。
- [ ] 寫入流程加防重與並發保護（序號與座位計算避免競態）。
- [ ] Google Sheet 欄位結構建立版本化檢查，避免手動改欄位造成寫入錯誤。

## P2 前端體驗（手機/高齡友善）
- [ ] 成功頁加入「每位參加者展開明細」卡片（票價 + 加購拆解）。
- [ ] 條款抽屜加「已閱讀後才可勾選同意」可選機制。
- [ ] 表單步驟加入「目前已填完整度」提示（例如 8/10 欄位）。
- [ ] 長者模式加入更高對比主題切換（字大 + 高對比）。
- [ ] 手機輸入優化：日期欄位加 fallback 提示與範例。

## P2 測試與交付
- [ ] 建立 pytest 自動測試：`validate_participant`、`build_registration_rows`、`build_payment_email_body`。
- [ ] 建立 API smoke tests：`/api/bootstrap`、`/api/register`、`/api/retry-email-queue`。
- [ ] 建立部署前檢查清單：環境變數完整性、敏感資料掃描、依賴版本鎖定。
- [ ] 新增 `README` 操作章節：本機啟動、.env、重送機制、常見錯誤排除。

## 完成定義（DoD）
- [ ] 本機與 Render 各跑 1 次單人、多人、SMTP 失敗不中斷測試。
- [ ] `email_sent=true` 的成功案例可重現，且重送佇列可清空。
- [ ] 前端手機版（iOS/Android）可完成從填寫到送出的完整流程。
- [ ] 所有新功能有對應文件與測試。