# COSMO API 從哪裡找到？如何取得使用者紀錄？

已完成並實測「網頁輸入暱稱 → 官方查帳號 → 公開鏈上合約列出全部持有 → 官方取得卡片基本資料」的流程。個人帳號與實際收藏紀錄不記錄在公開範例中。持有清單直接來自 Abstract 的 Objekt 合約，這條流程不依賴 Apollo 網頁或其資料庫；轉送歷史尚未實作。

## 先跑一個小範例

在專案根目錄執行：

```powershell
python -X utf8 -c "from pprint import pprint; from cosmo import fetch_public_account; pprint(fetch_public_account(input('COSMO 暱稱：').strip()), sort_dicts=False)"
```

輸入自己的 COSMO 暱稱後，成功時會得到兩個欄位。以下是欄位示意，實際值由查詢結果決定：

```python
{
    'nickname': '<你輸入的暱稱>',
    'address': '<官方回傳的錢包地址>'
}
```

輸入是公開 COSMO ID，流程是送出一次 GET 並檢查回應，輸出是暱稱與錢包地址。這份回應本身沒有持有卡片清單。

## API 的線索來源

本次依據 Apollo 的公開原始碼追查，再從本機實際發出請求核對回應。來源不是官方對第三方開發者的穩定 API 文件；位於官方網域，也不代表每條路徑都可公開使用或永久不變。

| 原始碼 | 找到什麼 |
| --- | --- |
| [types/common.ts](https://github.com/teamreflex/cosmo-web/blob/main/packages/cosmo/src/types/common.ts) | `COSMO_ENDPOINT`，即 `https://api.cosmo.fans` |
| [server/user.ts](https://github.com/teamreflex/cosmo-web/blob/main/packages/cosmo/src/server/user.ts) | `fetchByNickname()` 與暱稱查詢路徑 |
| [server/metadata.ts](https://github.com/teamreflex/cosmo-web/blob/main/packages/cosmo/src/server/metadata.ts) | `fetchMetadataV3()` 與單張卡片資料路徑 |
| [objekt-blockchain.ts](https://github.com/teamreflex/cosmo-web/blob/main/apps/web/src/lib/functions/objekts/objekt-blockchain.ts) | Apollo 個人持有清單查詢自己的鏈上索引資料庫 |

閱讀時，先找 `.get(...)` 的路徑，再檢查 `headers` 是否帶有登入資訊，以及回應使用哪個 schema。瀏覽器的 Network 面板也能觀察公開網站的 Fetch/XHR 請求；手機 App 的請求不會自動出現在桌面瀏覽器的 Network 面板。

## Proxy 如何看到 App 的網路請求？

Proxy 是放在通訊路徑中的「中繼站」。使用 mitmproxy 觀察自己手機的 App 流量時，概念如下：

```text
手機 COSMO App ⇄ 電腦上的 mitmproxy ⇄ COSMO 伺服器
                 在這裡觀察請求與回應
```

1. 手機把相關連線交給電腦上的 Proxy，由它轉送給 COSMO。
2. 你在 App 打開某個頁面。如果 App 發出網路請求，Proxy 就有機會看到目的地、方法、路徑、參數與伺服器回應。
3. HTTPS 的內容原本經過加密，一般 Proxy 只能轉送。mitmproxy 需要手機／App 信任它的測試憑證，才能分別與手機、伺服器建立加密連線，在中間讀取內容。部分 App 的憑證固定機制會拒絕此方式；本專案尚未實測目前 COSMO App 的攔截設定。

這能幫助研究「App 呼叫了哪個介面」，不代表 Proxy 自己擁有你的完整歷史。要讀取過去的使用紀錄，仍需 COSMO 有提供對應資料、App 實際請求它，並具備必要的帳號權限。開啟觀察前沒有經過 Proxy 的內容，也不會自動出現在工具裡。原理見 [mitmproxy 運作方式](https://docs.mitmproxy.org/stable/concepts/how-mitmproxy-works/) 與 [憑證說明](https://docs.mitmproxy.org/stable/concepts/certificates/)。

因此，目前不能下結論說「COSMO App 沒有拒絕第三方攔截，所以讀得到使用者資料」。本專案驗證的是 Python 可直接讀取特定公開介面與鏈上持有資料；App 是否信任測試憑證、是否有憑證固定機制，沒有在本機測試。公開帳號／目前持有資料，也不等於私有使用紀錄。

本次沒有安裝或設定手機 Proxy。輸入暱稱讀取目前持有收藏，沿用已驗證的公開帳號介面、鏈上持有枚舉及 metadata，可以直接由 Python 請求。

## Apollo 的作者如何找到資料？

如果上游沒有提供適合使用的開發者文件，常見的研究方法是觀察 App 實際送出的 HTTP 請求，辨認網域、路徑、參數與回應結構，再實測每個介面的用途。Apollo 專案也有 [proxy 工具](https://github.com/teamreflex/cosmo-web/blob/main/apps/proxy/README.md)，文件說明這些 mitmproxy 附加程式用來擷取 COSMO 手機 App 的卡片媒體，下載到本機，不會直接連接 Apollo。這能證明專案使用這類研究工具，但不能據此斷定作者第一次發現每條 API 的歷史過程。

取得目前持有清單，Apollo 使用另一種資料來源：它的 [processor.ts](https://github.com/teamreflex/cosmo-web/blob/main/apps/indexer/src/processor.ts) 監聽 Abstract 上 Objekt 合約的 `Transfer` 事件；[main.ts](https://github.com/teamreflex/cosmo-web/blob/main/apps/indexer/src/main.ts) 依轉移接收者更新 `owner`，搭配 COSMO metadata 建立索引資料庫。網頁再查詢這份資料庫，能快速支援大量帳號、排序與歷史。

我們目前只需要取得一個人的完整持有清單，因此可直接使用合約已提供的持有枚舉函式，不必先建立整套歷史索引。

## 目前已驗證的兩個官方查詢

帳號查詢：

```text
GET https://api.cosmo.fans/bff/v3/users/by-nickname/<NICKNAME>
```

單張卡片資料：

```text
GET https://api.cosmo.fans/bff/v3/objekts/nft-metadata/<TOKEN_ID>
```

請將 `<NICKNAME>` 與 `<TOKEN_ID>` 換成要查詢的暱稱及卡片 ID。單卡回應含 `name`、`image` 與 `attributes`。`attributes` 內的 `Artist`、`Member`、`Season`、`Collection`、`Class`，由 `cosmo.py` 轉成容易供網頁使用的欄位。V3 metadata 不是完整卡款資料模型；目前只使用實際存在且已驗證的基本欄位。

這兩個查詢本次不需要登入 Cookie 或 Token。Apollo 原始碼中另有需要 token、session 或解密處理的查詢，不能把本次的公開讀取方式直接套用到所有介面。

## 「使用者紀錄」要分開看

| 需求 | 取得方式與目前進度 |
| --- | --- |
| 公開帳號與錢包地址 | 官方暱稱查詢；已加入 `fetch_public_account()` |
| 指定 Token ID 的圖片、成員、季節、卡款代碼 | 官方 metadata；已加入 `fetch_objekt_metadata()` |
| 目前持有的全部 Token ID | 已透過 Abstract Objekt 合約的 `balanceOf()` 與 `tokenOfOwnerByIndex()`，在同一個區塊完整列出 |
| 轉送、購入等歷史 | 需要對應事件／歷史查詢；本次未實作 |

目前已實作的流程是：

```text
COSMO ID
  ↓ 官方暱稱查詢
錢包地址
  ↓ Abstract Objekt 合約 balanceOf + tokenOfOwnerByIndex
持有的 Token ID 清單
  ↓ 官方 metadata，支援 Unit 多成員卡片
我們的資料格式與網頁
```

完整收藏可從網頁輸入暱稱，經 `api.py`、`collection_jobs.py` 呼叫同步流程；`sync_collection.py` 是保留的命令列排查／備援工具。早期 Apollo 第一頁與單卡展示範例已在資料夾清理時移除，舊資料保存在本機備份。啟動方式見 [README](../README.md)，逐檔教學見 [TEACHING](TEACHING.md)。

## 鏈上持有清單怎麼查？

[Abstract 官方連線文件](https://docs.abs.xyz/connect-to-abstract) 列出主網 RPC 為 `https://api.mainnet.abs.xyz`、Chain ID 為 2741。Objekt 合約地址由 Apollo 的 [Addresses](https://github.com/teamreflex/cosmo-web/blob/main/packages/util/src/index.ts) 與 [合約函式 ABI](https://github.com/teamreflex/cosmo-web/blob/main/apps/indexer/src/abi/objekt/functions.ts) 核對：

```text
0x99bb83ae9bb0c0a6be865cacf67760947f91cb70
```

ABI 是合約函式的介面描述，會說明函式名稱、參數與回傳值。`chain.py` 使用的是公開唯讀 `eth_call`：

1. 取得本次的區塊號碼與雜湊，固定資料時點。
2. `balanceOf(address)` 讀取持有總數 `total`。
3. `tokenOfOwnerByIndex(address, index)` 從索引 0 到 `total - 1` 列出 Token ID。Multicall3 的 `aggregate3` 每次合併最多 200 個呼叫，同時查詢兩批。聚合結果不符或節點拒絕聚合時，會改查每批最多 50 筆的直接呼叫。
4. 確認筆數、唯一性及區塊雜湊後，網頁先取得持有清單。後端重用連線，分批送出已取得的官方卡片 metadata。
5. 卡片資料全部成功後，再核對區塊雜湊並保存完整快照。少數卡片資料缺少時，網頁仍可瀏覽已核對的持有清單。

Multicall3 透過 `eth_call` 合併多個唯讀呼叫。Abstract 主網的部署地址為 `0xaa4de41dba0ca5dcbb288b7cc6b708f3aac759e7`。參考 [Abstract 部署定義](https://github.com/wevm/viem/blob/main/src/chains/definitions/abstract.ts) 與 [Multicall3 原始碼](https://github.com/mds1/multicall3/blob/main/src/Multicall3.sol)。

這些呼叫不會送出交易，也不需要登入 Cookie、私鑰或錢包簽名。亦可用 `ownerOf()` 抽查卡片是否屬於指定的查詢錢包。

持有資料每次都重新讀取；圖片與卡款 metadata 最多快取 24 小時，避免反覆查詢相同資料。快取按鏈、合約、Token ID 分開存放，不能將 Token ID 當成跨鏈的全域識別碼。目前完整性範圍是 Abstract 上這個 COSMO Objekt 合約，並非所有鏈、所有 NFT 合約的錢包資產。

程式已移除每帳號 10,000 張的人工上限，會按 `total` 完整查完所有批次；網頁每頁 60 張不影響取得總數。大量資料仍受網路、來源服務與記憶體影響，失敗不發布部分快照。Unit 卡會保留例如 `S4 X S18` 的組合名稱，以及 `ChaeYeon`、`JooBin` 的個別成員，讓成員篩選仍能找到組合卡。

單卡 metadata 不會證明目前持有人。名稱尾端的數字也不能當成已驗證的發行序號。網頁會明確標示 Token ID，不自行填入可傳送狀態、Grid 使用情況或發行序號。
