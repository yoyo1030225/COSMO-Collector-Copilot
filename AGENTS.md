# COSMO Collector Copilot：協作與教學說明

## 工作方式

- 使用繁體中文說明，程式、函式與變數採英文命名。
- 先閱讀 AGENTS.md、HANDOFF.md、README.md，檢查現有程式與 Git 狀態，保留使用者修改。一次處理一個清楚的小任務。
- 使用者透過本機 VS Code／Codex 讀寫、執行與測試，再依當次指示同步 GitHub。環境快照、Git 推送與網站部署是不同操作。
- 2026-11-19 此目錄仍沒有 `.git`。不要自行初始化、提交、推送或部署。

## 教學偏好

- 使用者有程式設計經驗，但希望用更簡單的步驟學習。
- 先提供小而完整、可執行的範例，再解釋輸入、流程與輸出。
- 可以先寫好核心函式，不預設使用者能從空白開始，不做連續測驗。
- 先閱讀與執行，再修改一個值，熟悉後逐步自行撰寫。
- 說明新功能的目的、檔案與資料流程；修改後解釋關鍵語法，執行適當驗證，指出正確性與可維護性問題。
- 主要教學統一維護在 `docs/TEACHING.md`，README 保持簡短；不要重新加入已被取代的入門程式。

## 目前目標與邊界

- 專案是 tripleS COSMO Objekt 收藏決策分析器。MVP 預計包含收藏資料、保留偏好、重複分析及手動登錄活動條件。
- 已授權逐步實作 Objekt 總覽與個人圖鑑，邊做邊學；目前完成的是個人持有圖鑑。
- 現有技術為 Nuxt 4／Vue 3／TypeScript、FastAPI／Pydantic，Python 核心查詢使用標準函式庫。
- 原預定 Nuxt 3，因當時依賴檢查採 Nuxt 4。保留 `ssr: false` 及 package.json 的既有依賴修正。
- SQLAlchemy、SQLite、pytest、登入、排程、交易歷史與收藏決策分析尚未引入，每次只增加一個可執行的小功能。
- 系統只提供讀取與決策輔助，不直接執行 Spin、交易或領獎，不把條件符合宣稱為必定獲獎。

## 現有執行流程

- `web/app/components/CollectionGallery.vue`：暱稱輸入、成功快照、搜尋、成員／季節篩選、每頁 60 張。
- `web/app/composables/useCollectionLookup.ts`：POST 建立工作，每秒 GET 讀取進度；成功才更新畫面，失敗保留原收藏。
- `api.py`：暱稱驗證、HTTP 路由與 BackgroundTasks。
- `collection_jobs.py`：單一背景工作、狀態與進度、按錢包保存成功快照。
- `cosmo.py`：官方公開帳號與 metadata 查詢，包含 Unit 多成員轉換。
- `chain.py`：Abstract 同一區塊的完整持有枚舉，批次 50 個 RPC 呼叫。
- `collection.py`：持有與 metadata 整合、24 小時 metadata 快取、完整性驗證與原子寫入。
- `sync_collection.py`：可選的命令列排查／備援工具，輸出 `web/public/data/collection.json`；API 快照優先。

執行 API（根目錄）：

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

另一個終端機在 `web/` 執行 `npm.cmd run dev`。API 使用單一程序，不加 `--workers`；記憶體工作編號在 API 重啟後失效，已保存快照仍在。

驗證：根目錄 `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`；網頁在 `web/` 執行 `npm.cmd run typecheck`、`npm.cmd run build`。整理後保留的 28 項 Python 測試通過。

## 資料模型與來源

- 暱稱 → 官方公開帳號／錢包 → Abstract Objekt 合約持有 Token ID → 官方 metadata。API 與 ABI 線索來自 Apollo 公開原始碼，再由本機實測核對；詳細來源在 `docs/cosmo-api.md`。
- RPC：`https://api.mainnet.abs.xyz`，Chain ID 2741，合約 `0x99bb83ae9bb0c0a6be865cacf67760947f91cb70`。
- 卡款與個別持有紀錄分開；同款多張以各自 Token ID 保存。Token ID 的識別範圍須搭配鏈與合約，發行序號不能當成全域 ID。
- 保留季節、完整卡款代碼及 A／Z 後綴。Unit 保留組合名稱與個別成員陣列。
- metadata 不證明持有人，不自行補發行序號、可傳送、鎖定偏好或 Grid 使用情況。Apollo 早期的 usedForGrid 固定 false 也不能證明未使用。
- 固定同一區塊取得持有清單，張數、唯一性、全部 metadata 及區塊雜湊通過才發布完整快照；失敗保留上次成功資料。每帳號上限 10,000 張。
- 持有每次重新查，metadata 最多快取 24 小時。API 快照位於忽略的 `data/collections/<chain>/<contract>/`，快取位於 `data/cosmo-metadata/`。
- 2026-11-19 17:49 網頁實測 `unproKPOPfan225`：719 張、564 款、5 張 Unit，區塊 89388494。667 是早期觀察值，不能當固定總數。
- mitmproxy 是觀察 App 流量的研究工具，目前未實測 COSMO App 的攔截／憑證設定；直接公開查詢成功不能證明 App 接受攔截，也不能推論取得所有私有歷史。

## 清理與接續

- 2026-11-19 已依使用者要求移除固定資料、Apollo 第一頁、單卡展示及對應舊測試／樣本，合計 19 個檔案；清單與還原方式見 `docs/TEACHING.md`。
- 清理前的 27 個檔案已備份並核對 SHA-256：`data/backups/cleanup-before-20261119-181352.zip`。包含使用者舊有 `PREVIEW_COUNT = 1` 修改；不要無故還原舊入口。
- `.venv`、Node 依賴、目前成功快照、metadata 快取與完整 JSON 備援保留。`data/`、環境變數與本地資料庫由 Git 忽略，不提交密碼、Cookie 或 Token。
- 下一步先帶使用者執行 `docs/TEACHING.md` 第 1 節，再讀 `lookupCollection()` → `useCollectionLookup()` → `api.py`，一次解釋一段。
