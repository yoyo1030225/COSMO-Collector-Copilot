# COSMO Collector Copilot：目前交接

更新日期為 2026-11-23（Asia/Taipei）。目前入口與程式以本文件、README 及 `docs/TEACHING.md` 為準，修改前先確認使用者的新指示與本機檔案。

## 工作區與已完成內容

- 工作區以本機 Git 儲存庫根目錄為準，不在文件記錄使用者的絕對路徑。使用者已推送至 GitHub；提交、推送及歷史改寫依當次授權處理。
- 使用者希望本機邊做邊學，繁體中文、先有可執行小範例再逐段解釋；保留現有修改，不做連續測驗。
- 送出暱稱後先顯示帳號，持有清單核對後可立即翻頁。卡片資料優先補目前頁面，再接續其餘收藏。重新整理回到空白輸入頁。圖鑑提供搜尋、成員／季節篩選與每頁 60 張。
- Nuxt 4.6.4／Vue 3／TypeScript 採 `ssr: false`。先前開發 SSR 工作者曾有記憶體問題，現在不需重新啟用。保留 package.json 的 minimatch 間接依賴修正與 package-lock.json。
- FastAPI 0.165.0、Uvicorn 0.54.0、測試 httpx 0.28.1 安裝在 `.venv`。Starlette TestClient 目前有 httpx 日後棄用提示，測試可通過，可另開小任務更新測試依賴。

## 啟動與資料流程

根目錄執行 `.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000`；另一終端機在 `web/` 執行 `npm.cmd run dev`。Nuxt 設定改變後，既有開發服務需要在原終端機重新啟動。

```text
CollectionGallery.vue → useCollectionLookup.ts → Nuxt /api/collections/**
  → api.py /collections/** → collection_jobs.py
  → cosmo.py 帳號 → collection.py → chain.py 持有 + cosmo.py metadata
  → 驗證持有清單 → 網頁先能翻頁 → 卡片資料分批補上 → 保存完整快照
```

- `POST /collections/sync` 回傳 HTTP 202 與工作編號。網頁帶 `cursor` 查 `GET /collections/jobs/<id>`，每次取得最多 300 張卡片資料。`include_tokens` 讓前端只在尚未收到時索取已核對的 Token ID 清單。不帶 `cursor` 的舊呼叫仍能取得成功快照。`GET /collections/latest` 讀取最近成功資料。
- `POST /collections/jobs/<id>/prioritize` 接受目前頁面尚待補齊的 Token ID，最多 60 筆。工作只排入該帳號已核對的 Token ID。下一個 worker 空位會優先補目前頁面。
- 同時只跑一個工作，相同暱稱沿用進行中工作，其他暱稱回覆 409。最多保存最近 20 個工作狀態於程序記憶體，不加 `--workers`；重啟後需重新建立工作編號。
- 前端每秒讀進度，有更多卡片資料可取時立即接續。單次請求用瀏覽器取消訊號限制為 10 秒。區塊重驗失效時撤回該次持有清單。只有個別 metadata 缺少時，畫面仍顯示已核對的持有紀錄，並可重新讀取補齊。
- API 成功資料保存於 `data/collections/2741/<contract>/<wallet>.json` 與 `latest.json`。錢包資料、張數與 Token ID 驗證通過才保存；沒有 SQLite。
- `sync_collection.py` 產生完整的 `web/public/data/collection.json` 供本機檢查。網頁送出新查詢後，使用 `preview` 顯示進行中的結果，`data` 另保存最後完整結果。
- metadata 快取在 `data/cosmo-metadata/2741/<contract>/`，有效 7 天。八個 worker 重用 HTTPS 連線，收到 HTTP 429 時共用暫停時間。使用系統 HTTPS proxy 時沿用 urllib。持有清單每次都從鏈上重新核對。

## 來源與正確性

- 官方公開帳號介面及 metadata 由 Apollo 原始碼找到，再從本機核對。持有來自 Abstract RPC，不需 Apollo 網頁或資料庫。
- RPC `https://api.mainnet.abs.xyz`，Chain ID 2741，Objekt 合約 `0x99bb83ae9bb0c0a6be865cacf67760947f91cb70`。
- 固定同一區塊，`balanceOf` 取張數。Multicall3 的 `aggregate3` 一批合併最多 200 次 `tokenOfOwnerByIndex`，同時執行兩批。拒絕聚合時改用每批 50 次直接呼叫。`upstream.py` 處理暫時性錯誤與限流。
- 持有清單在送出前檢查張數、唯一性與區塊雜湊，卡片資料完成後再查區塊雜湊。Unit 同時保存組合名稱與個別成員。只在所有 metadata 成功後保存完整快照。
- 不從 metadata 推斷發行序號、可傳送狀態或 Grid 使用情況；不把 Token ID 當跨鏈全域 ID。
- 已實測完整持有清單、筆數與 Token ID 唯一性、Unit 多成員；個人帳號、真實張數、區塊、持有時點及個別卡片 ID 已從受版本控制的範例移除。
- 前一輪瀏覽器驗證：暱稱查詢、錯誤時保留舊資料、空白停用、最後一頁、成員篩選含 Unit、重新整理恢復 API 快照、375px 兩欄及 1440px 六欄。本機截圖在 Git 忽略的 `data/research/`。
- 沒有實測目前 COSMO App 的 mitmproxy 攔截。公開介面可讀與 App 是否信任測試憑證是不同問題；不能宣稱抓到全部使用歷史。

## 本次資料夾清理

- 移除 19 個無目前引用的舊範例、對應測試、單張資料與研究樣本，細目見 `docs/TEACHING.md` 第 13 節。
- 備份：`data/backups/cleanup-before-20261119-181352.zip`，含 27 個清理前檔案、原路徑與 SHA-256 清單。包含使用者舊有 `read_collection.py` 的 `PREVIEW_COUNT = 1` 及離線 Apollo 來源。
- 清掉單卡展示 CSS／型別，將 `Objekt.members` 改為必要欄位，與既有資料驗證一致；保留所有目前執行入口、完整 JSON 備援、快照、快取及已安裝依賴。
- README、web/README、AGENTS、HANDOFF 已精簡；完整逐檔與關鍵程式教學統一放 `docs/TEACHING.md`；資料來源與 Proxy 保留於 `docs/cosmo-api.md`。
- 目前 36 項 Python 測試、7 項網頁測試、Nuxt 型別檢查與正式建置通過。以 10,001 筆人工資料驗證同步期間跳到第 167 頁，末頁 41 張的資料會優先完成。也模擬了限流、快取到期及單張卡片資料缺少。
- 本次瀏覽器確認預設空白輸入、空白時停用提交、錯誤暱稱不帶出舊資料、重新整理回到空白頁，以及 375px 手機直排無溢出。截圖在 Git 忽略的 `data/research/collection-entry-desktop.jpg` 與 `collection-entry-mobile.jpg`。
- 本次 QA 使用獨立的 3001 與 8001 埠。截圖位於忽略的 `data/research/collection-large-progress.jpg`。Python 變更須由原終端機重新啟動 API 才生效。

## 下一步

本次依使用者要求清理程式、測試、UI 提示和文件中的個人資訊，CLI 改為執行時輸入暱稱。測試使用人工暱稱、地址與 Token ID；公開的系統合約地址保留。Git 忽略的本機收藏、快取與備份保留，既有 GitHub 提交仍含先前內容；尚未提交、推送或改寫歷史。

2026-11-23 已將教學更新至 33 個自訂檔案，補充先顯示帳號、分批接收卡片、Multicall3 與錯誤情境。小量公開合約對照中，同區塊 200 次讀取用四批直接呼叫耗時 4.86 秒，合併一次耗時 0.86 秒。整個收藏的等待時間仍取決於卡片資料來源與快取。

先帶使用者跑 `docs/TEACHING.md` 第 1 節的單次帳號查詢，再按一次網頁「讀取收藏」。閱讀順序：`lookupCollection()` → `useCollectionLookup()` → `api.py` 的 `BackgroundTasks`，接著才看鏈上參數編碼。暫不擴充新功能。
