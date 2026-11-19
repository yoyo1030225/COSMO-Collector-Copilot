# 個人 Objekt 圖鑑網頁

這是 Nuxt 4／Vue 3／TypeScript 的客戶端網頁，功能是暱稱查詢、完整持有統計、搜尋、成員／季節篩選及每頁 60 張的分頁。

在專案根目錄另開終端機啟動 Python API：

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

在本目錄執行 `npm.cmd run dev`，打開終端機輸出的網址。輸入 COSMO 暱稱並按「讀取收藏」。首次取得專案先執行 `npm.cmd ci`。

閱讀順序：`app/app.vue` → `app/components/CollectionGallery.vue` → `app/composables/useCollectionLookup.ts` → 根目錄 `api.py`。每個檔案與關鍵語法統一整理在 [完整教學](../docs/TEACHING.md)，啟動與驗證方式見 [專案 README](../README.md)。

`nuxt.config.ts` 將 `/api/collections/**` 轉送到本機 `127.0.0.1:8000/collections/**`，這與觀察手機流量的 mitmproxy 是不同用途。API 只供目前本機使用。

修改後執行 `npm.cmd run typecheck` 與 `npm.cmd run build`。`package-lock.json` 用來重現安裝；`node_modules/`、`.nuxt/`、`.output/` 是依賴或產生檔案，已由 Git 忽略。
