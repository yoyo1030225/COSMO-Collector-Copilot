# 個人 Objekt 圖鑑網頁

這是 Nuxt 4／Vue 3／TypeScript 的客戶端網頁。開頁先顯示空白暱稱輸入頁。找到帳號後即可看到暱稱與查詢進度，持有清單核對後可以翻頁，卡片資料陸續出現。重新整理會回到輸入頁。

在專案根目錄另開終端機啟動 Python API：

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

在本目錄執行 `npm.cmd run dev`，打開終端機輸出的網址。輸入 COSMO 暱稱並按「讀取收藏」。首次取得專案先執行 `npm.cmd ci`。

閱讀順序：`app/app.vue` → `app/components/CollectionGallery.vue` → `app/composables/useCollectionLookup.ts` → 根目錄 `api.py`。每個檔案與關鍵語法統一整理在 [完整教學](../docs/TEACHING.md)，啟動與驗證方式見 [專案 README](../README.md)。

`nuxt.config.ts` 將 `/api/collections/**` 轉送到本機 `127.0.0.1:8000/collections/**`，這與觀察手機流量的 mitmproxy 是不同用途。API 只供目前本機使用。

修改後執行 `npm.cmd test`、`npm.cmd run typecheck` 與 `npm.cmd run build`。`tests/collection-gallery.test.mjs` 驗證空白首頁、10,001 筆資料的最後一頁、分批回應組合，以及卡片資料缺少時的顯示。`package-lock.json` 用來重現安裝。

每頁顯示 60 張。瀏覽器先取得 Token ID，再按 `cursor` 接收每批最多 300 張卡片資料。翻頁時會送出該頁待補的 Token ID，讓 API 優先讀取。資料尚未補齊時可以用 Token ID 搜尋，成員與季節選項會隨資料更新。設定與測試範例見 [教學第 14 節](../docs/TEACHING.md#14-數量時間與大量收藏)。
