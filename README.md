# COSMO Collector Copilot

以 tripleS COSMO Objekt 為主題的收藏決策分析工具。目前已完成「輸入 COSMO 暱稱 → 讀取完整持有收藏 → 搜尋、篩選與分頁」的本機網頁。

2026-11-19 實測 `unproKPOPfan225` 有 719 張、564 款，含 5 張 Unit 組合卡。張數會變動，畫面會顯示持有時點與最後成功同步時間。

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

開啟終端機印出的網址，通常是 [http://127.0.0.1:3000](http://127.0.0.1:3000)。輸入 `unproKPOPfan225`，按「讀取收藏」。若原本已有 Nuxt 運行，請在它的終端機 Ctrl+C 後重新啟動，載入目前設定。

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
sync_collection.py     可選的命令列同步工具
tests/                 目前功能的離線測試
web/                   Nuxt／Vue 網頁
docs/                  教學與資料來源說明
data/                  本機快照、metadata 快取、備份（Git 忽略）
```

按「讀取收藏」才重新查詢持有狀態。全部成功且驗證通過才更新圖鑑；失敗保留上一份成功資料。重新整理先讀 API 保存的快照，API 不可用或尚無快照時會嘗試本機完整 JSON 備援。

可選的命令列工具：`python -X utf8 sync_collection.py`。帳號設定在該檔的 `USERNAME`，輸出 `web/public/data/collection.json`；這是網頁的備援來源，API 的最近成功快照優先。

## 驗證

在根目錄執行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

在 `web/` 執行：

```powershell
npm.cmd run typecheck
npm.cmd run build
```

整理後 28 項 Python 測試、型別檢查與建置通過。測試使用人工資料或模擬請求，不依賴真實帳號或本機 `data/`。

## 範圍與本機資料

目前讀取 Abstract 上指定 COSMO Objekt 合約的持有清單，不包含轉送／購入歷史、Grid 使用情況、發行序號或可傳送狀態。每帳號上限 10,000 張；超過時明確中止。圖片與卡款 metadata 最多快取 24 小時，持有清單每次重查。

專案尚未加入資料庫、登入、定時同步或收藏決策分析。程式只讀資料，不執行 Spin、交易或獎勵領取。

2026-11-19 檢查時，資料夾沒有 `.git`，無法與 GitHub 比較差異。這次清理前已建立忽略的本機備份 `data/backups/cleanup-before-20261119-181352.zip`，未初始化 Git、提交、推送或部署。請勿提交 `data/`、`.env`、密碼或登入 Token。
