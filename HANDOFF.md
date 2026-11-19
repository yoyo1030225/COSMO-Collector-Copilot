# COSMO Collector Copilot：目前交接

更新：2026-11-19（Asia/Taipei）。目前入口與程式以本文件、README 及 `docs/TEACHING.md` 為準，修改前先確認使用者的新指示與本機檔案。

## 工作區與已完成內容

- 工作區：`C:\Users\yoyo1\Documents\Code\COSMO-Collector-Copilot`。目錄仍沒有 `.git`，無法比較與 GitHub 的差異；本次沒有初始化 Git、提交、推送或部署。
- 使用者希望本機邊做邊學，繁體中文、先有可執行小範例再逐段解釋；保留現有修改，不做連續測驗。
- 已完成輸入 COSMO 暱稱讀取完整個人持有收藏，以及統計、搜尋、成員／季節篩選、每頁 60 張。尚未實作所有卡款總覽、資料庫、登入、定時同步、轉移歷史或決策分析。
- Nuxt 4.6.4／Vue 3／TypeScript 採 `ssr: false`。先前開發 SSR 工作者曾有記憶體問題，現在不需重新啟用。保留 package.json 的 minimatch 間接依賴修正與 package-lock.json。
- FastAPI 0.165.0、Uvicorn 0.54.0、測試 httpx 0.28.1 安裝在 `.venv`。Starlette TestClient 目前有 httpx 日後棄用提示，測試可通過，可另開小任務更新測試依賴。

## 啟動與資料流程

根目錄執行 `.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000`；另一終端機在 `web/` 執行 `npm.cmd run dev`。Nuxt 設定改變後，既有開發服務需要在原終端機重新啟動。

```text
CollectionGallery.vue → useCollectionLookup.ts → Nuxt /api/collections/**
  → api.py /collections/** → collection_jobs.py
  → cosmo.py 帳號 → collection.py → chain.py 持有 + cosmo.py metadata
  → 完整驗證 → 成功快照 → API → 畫面更新
```

- `POST /collections/sync` 回傳 HTTP 202 與工作編號；`GET /collections/jobs/<id>` 回報狀態、進度、錯誤或快照；`GET /collections/latest` 讀取最近成功資料；`GET /health` 檢查服務。
- 同時只跑一個工作，相同暱稱沿用進行中工作，其他暱稱回覆 409。最多保存最近 20 個工作狀態於程序記憶體，不加 `--workers`；重啟後需重新建立工作編號。
- 前端每秒讀進度，最多等待 15 分鐘；卸載元件只停止前端等待，不取消 Python 工作。查詢期間及失敗後保留舊圖鑑並標示帳號。
- API 成功資料保存於 `data/collections/2741/<contract>/<wallet>.json` 與 `latest.json`。錢包資料、張數與 Token ID 驗證通過才保存；沒有 SQLite。
- `sync_collection.py` 是保留的 CLI，產生 `web/public/data/collection.json` 備援。網頁初次載入優先讀 API；不可用或尚無資料時讀備援 JSON；都無效時顯示輸入提示。
- metadata 快取在 `data/cosmo-metadata/2741/<contract>/`，有效 24 小時；持有清單每次重新查。暫存檔使用不同名稱，原子替換目標；Windows 的短暫鎖定有有限重試。

## 來源與正確性

- 官方公開帳號介面及 metadata 由 Apollo 原始碼找到，再從本機核對。持有來自 Abstract RPC，不需 Apollo 網頁或資料庫。
- RPC `https://api.mainnet.abs.xyz`，Chain ID 2741，Objekt 合約 `0x99bb83ae9bb0c0a6be865cacf67760947f91cb70`。
- 固定同一區塊，`balanceOf` 取張數，`tokenOfOwnerByIndex` 列出所有 Token ID，每批 50 筆；還原 RPC 回應順序並拒絕缺筆、重複及錯誤。最多 10,000 張，超過明確拒絕。
- 所有 metadata 成功，再核對區塊雜湊，才回傳完整快照。個別 Token ID 與卡款不同，同款多張保留。Unit 同時保存組合名稱與個別成員。
- 不從 metadata 推斷發行序號、可傳送狀態或 Grid 使用情況；不把 Token ID 當跨鏈全域 ID。
- 17:49 網頁實測 `unproKPOPfan225`：719 張、564 款、719 個不同 Token ID、5 張 Unit；區塊 89388494。持有時點 17:49:24，完成 17:49:43。667 是早期值。
- 前一輪瀏覽器驗證：真實暱稱、錯誤暱稱保留舊資料、空白停用、第 12 頁 59 張、ChaeYeon 篩選含 Unit、重新整理恢復 API 快照、375px 兩欄及 1440px 六欄。截圖在 `data/research/nickname-lookup-*.jpg`。
- 沒有實測目前 COSMO App 的 mitmproxy 攔截。公開介面可讀與 App 是否信任測試憑證是不同問題；不能宣稱抓到全部使用歷史。

## 本次資料夾清理

- 移除 19 個無目前引用的舊範例、對應測試、單張資料與研究樣本，細目見 `docs/TEACHING.md` 第 13 節。
- 備份：`data/backups/cleanup-before-20261119-181352.zip`，含 27 個清理前檔案、原路徑與 SHA-256 清單。包含使用者舊有 `read_collection.py` 的 `PREVIEW_COUNT = 1` 及離線 Apollo 來源。
- 清掉單卡展示 CSS／型別，將 `Objekt.members` 改為必要欄位，與既有資料驗證一致；保留所有目前執行入口、完整 JSON 備援、快照、快取及已安裝依賴。
- README、web/README、AGENTS、HANDOFF 已精簡；完整逐檔與關鍵程式教學統一放 `docs/TEACHING.md`；資料來源與 Proxy 保留於 `docs/cosmo-api.md`。
- 整理後 28 項 unittest、Nuxt 型別檢查與正式建置通過。原本 41 項中的 13 項屬被刪除的 importer／Apollo 教學，不是目前收藏功能的測試。
- 本次沒有啟動或接管使用者的服務。前次觀察到使用者在 3000 埠的 Nuxt PID 為 36652，接手時請重新確認，勿把它當成可直接關閉的 QA 程序。

## 下一步

先帶使用者跑 `docs/TEACHING.md` 第 1 節的單次帳號查詢，再按一次網頁「讀取收藏」。閱讀順序：`lookupCollection()` → `useCollectionLookup()` → `api.py` 的 `BackgroundTasks`，接著才看鏈上參數編碼。暫不擴充新功能。
