# COSMO Collector Copilot

以 tripleS COSMO Objekt 為主題的收藏決策分析工具。目前已完成「輸入 COSMO 暱稱 → 讀取完整持有收藏 → 搜尋、篩選與分頁」的本機網頁。

已驗證完整持有讀取與 Unit 組合卡處理。張數依查詢帳號而定，畫面會顯示持有時點與最後成功同步時間。

## 先執行

第一個終端機在專案根目錄啟動 API，保持開著：

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

第二個終端機從根目錄啟動網頁：

```powershell
cd web
npm.cmd run dev
```

開啟終端機印出的網址，通常是 [http://127.0.0.1:3000](http://127.0.0.1:3000)。輸入自己的 COSMO 暱稱，按「讀取收藏」。若原本已有 Nuxt 運行，請在它的終端機 Ctrl+C 後重新啟動，載入目前設定。

每次開啟或重新整理都先顯示空白輸入頁。送出暱稱後，畫面先顯示查到的帳號。核對持有清單後就能翻頁，卡片的名稱、分類與圖片會陸續補上。若原本已有 Python API 運行，請在它的終端機按 Ctrl+C，再執行上方 API 命令載入新版。

本機已安裝依賴。新取得專案時，先在根目錄執行一次：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd web
npm.cmd ci
```

使用 Python 3.12 以上及 Node.js 22 以上。API 目前採單一程序，不加 `--workers`。

## 如何讀這個專案

先閱讀 [逐檔功能與關鍵程式碼教學](docs/TEACHING.md)。其中包含：

- 一個只查暱稱的可執行小範例。
- 自行維護的每個檔案、資料夾與閱讀順序。
- Python、FastAPI、Vue／TypeScript 的實際程式片段與解釋。
- 快照、快取、完整性檢查與失敗保留的原因。
- 本次刪除清單及備份還原方式。

[API 與 Proxy 說明](docs/cosmo-api.md) 記錄來源線索、已驗證的端點、鏈上合約及 mitmproxy 的用途。[web/README.md](web/README.md) 是網頁端的簡短操作索引。

## 現在的檔案結構

```text
api.py                 FastAPI 路由與暱稱驗證
collection_jobs.py     背景工作、進度與成功快照保存
collection.py          持有清單與卡片基本資料的整合
chain.py               Abstract 同區塊持有查詢
cosmo.py               官方帳號與 metadata 查詢／轉換
upstream.py            上游唯讀請求的限流與連線重試
sync_collection.py     可選的命令列同步工具
tests/                 目前功能的離線測試
web/                   Nuxt／Vue 網頁
docs/                  教學與資料來源說明
data/                  本機快照、metadata 快取、備份（Git 忽略）
```

圖鑑先列出已驗證的 Token ID，再逐批顯示卡片資料。個別卡片資料取得失敗時，持有清單仍可瀏覽，重新讀取可利用既有快取補齊。只有全部資料驗證通過才保存完整快照。

可選的命令列工具：`python -X utf8 sync_collection.py`。執行後在終端機輸入 COSMO 暱稱，匯出 `web/public/data/collection.json` 供本機檢查；網頁不會自動讀取這份匯出檔。API 仍會保存成功快照，但不會在開頁時自動顯示。

## 驗證

在根目錄執行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

在 `web/` 執行：

```powershell
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
```

目前 33 項 Python 測試、5 項網頁測試、型別檢查與建置通過。測試包括 10,001 筆人工資料、末頁分批傳輸及單張卡片資料缺少的情境。

## 範圍與本機資料

目前讀取 Abstract 上指定 COSMO Objekt 合約的持有清單。每頁顯示 60 張，切換頁碼後會優先補該頁的卡片資料，其餘卡片在背景繼續讀取。鏈上讀取使用 Multicall3 合併請求。COSMO 卡片資料以最多 8 路並行讀取並快取 7 天，持有清單每次仍重新查詢。首次讀取大型收藏的總耗時取決於網路與來源服務。

專案尚未加入資料庫、登入、定時同步或收藏決策分析。程式只讀資料，不執行 Spin、交易或獎勵領取。

專案已建立 Git 並推送至 GitHub。程式、文件與測試使用通用或人工範例，不寫入個人暱稱、錢包地址、本機帳號路徑或真實收藏紀錄。既有提交仍可能保留先前內容，清理目前檔案不會自動移除 Git 歷史。

清理前的本機備份位於忽略的 `data/backups/`，與其他本機資料一樣不應提交。請勿提交 `data/`、`.env`、密碼或登入 Token。
