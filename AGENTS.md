# COSMO Collector Copilot：協作與教學說明

## 工作方式

- 使用繁體中文說明，程式、函式與變數採英文命名。
- 先閱讀 AGENTS.md、HANDOFF.md、README.md，檢查現有程式與 Git 狀態，保留使用者修改。一次處理一個清楚的小任務。
- 使用者透過本機 VS Code／Codex 讀寫、執行與測試，再依當次指示同步 GitHub。環境快照、Git 推送與網站部署是不同操作。
- 使用者已建立 Git 並推送至 GitHub。提交、推送、部署與歷史改寫依使用者當次授權處理，不自行執行。
- 程式、文件、測試與 UI 範例不寫入個人暱稱、錢包地址、本機帳號路徑或真實持有紀錄；查詢時由使用者輸入，測試用人工資料。

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

- `web/app/components/CollectionGallery.vue`：預設空白輸入頁，送出暱稱後依序顯示帳號、已核對的持有清單和卡片資料。重新整理回到輸入頁。搜尋、成員／季節篩選、每頁 60 張。
- `web/app/composables/useCollectionLookup.ts`：POST 建立工作，以 `cursor` 接續進度與新取得的卡片，並通知 API 優先讀取目前頁面。完整驗證後才替換成功快照。
- `api.py`：暱稱驗證、HTTP 路由與 BackgroundTasks。
- `collection_jobs.py`：單一背景工作、狀態與進度、按錢包保存成功快照。
- `cosmo.py`：官方公開帳號與 metadata 查詢，包含 Unit 多成員轉換。
- `chain.py`：Abstract 同一區塊的完整持有枚舉，Multicall3 每批最多 200 個合約呼叫，同時最多兩批，聚合遭拒時能改用 50 筆直接呼叫。
- `collection.py`：持有與 metadata 整合、目前頁面優先、8 路並行讀取、7 天快取、完整性驗證與原子寫入。
- `upstream.py`：唯讀的 COSMO 與 RPC 查詢遇暫時性錯誤或限流時有限重試。
- `sync_collection.py`：可選的命令列排查／匯出工具，輸出 `web/public/data/collection.json`；網頁不自動讀取匯出檔。

執行 API（根目錄）：

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

另一個終端機在 `web/` 執行 `npm.cmd run dev`。API 使用單一程序，不加 `--workers`；記憶體工作編號在 API 重啟後失效，已保存快照仍在。

驗證方式見 README。目前 36 項 Python、7 項網頁測試、型別檢查及建置通過。

## 資料模型與來源

- 暱稱 → 官方公開帳號／錢包 → Abstract Objekt 合約持有 Token ID → 官方 metadata。API 與 ABI 線索來自 Apollo 公開原始碼，再由本機實測核對；詳細來源在 `docs/cosmo-api.md`。
- RPC：`https://api.mainnet.abs.xyz`，Chain ID 2741，合約 `0x99bb83ae9bb0c0a6be865cacf67760947f91cb70`。
- 卡款與個別持有紀錄分開；同款多張以各自 Token ID 保存。Token ID 的識別範圍須搭配鏈與合約，發行序號不能當成全域 ID。
- 保留季節、完整卡款代碼及 A／Z 後綴。Unit 保留組合名稱與個別成員陣列。
- metadata 不證明持有人，不自行補發行序號、可傳送、鎖定偏好或 Grid 使用情況。Apollo 早期的 usedForGrid 固定 false 也不能證明未使用。
- 固定同一區塊取得持有清單，核對張數、唯一性及區塊雜湊後即可瀏覽。metadata 缺少時保留已核對的持有紀錄，驗證完整資料後才保存新的完整快照。
- 持有每次重新查，metadata 最多快取 7 天。API 快照位於忽略的 `data/collections/<chain>/<contract>/`，快取位於 `data/cosmo-metadata/`。
- 已實測完整持有查詢與 Unit 處理；不在版本控制文件保留個人帳號、實際張數、持有時點、區塊及個別 Token ID。總數依查詢結果而定。
- mitmproxy 是觀察 App 流量的研究工具，目前未實測 COSMO App 的攔截／憑證設定；直接公開查詢成功不能證明 App 接受攔截，也不能推論取得所有私有歷史。

## 清理與接續

- 2026-11-19 已依使用者要求移除固定資料、Apollo 第一頁、單卡展示及對應舊測試／樣本，合計 19 個檔案；清單與還原方式見 `docs/TEACHING.md`。
- 清理前的 27 個檔案已備份並核對 SHA-256：`data/backups/cleanup-before-20261119-181352.zip`。包含使用者舊有 `PREVIEW_COUNT = 1` 修改；不要無故還原舊入口。
- `.venv`、Node 依賴、目前成功快照、metadata 快取與 JSON 匯出檔保留。`data/`、環境變數與本地資料庫由 Git 忽略，不提交密碼、Cookie 或 Token。
- 下一步先帶使用者執行 `docs/TEACHING.md` 第 1 節，再讀 `lookupCollection()` → `useCollectionLookup()` → `api.py`，一次解釋一段。
- `sync_collection.py` 執行時提示輸入暱稱，沒有固定個人帳號。這次去識別只更新目前檔案，既有 Git 提交尚未清理；本機忽略資料保留。
- 2026-11-20 已更新完整教學，涵蓋目前 32 個自訂檔案、關鍵程式碼、讀取流程與大量收藏。新增 `web/tests/collection-gallery.test.mjs`；10,001 筆皆為人工資料，不是真實收藏或效能保證。
- 2026-11-23 更新大量收藏流程與教學。以 10,001 筆人工資料驗證帳號先顯示、讀取期間可翻到第 167 頁、缺少單張 metadata 時持有數仍完整。
