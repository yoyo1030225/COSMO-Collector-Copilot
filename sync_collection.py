"""執行 python -X utf8 sync_collection.py，匯出完整收藏 JSON。"""

from pathlib import Path
from urllib.error import HTTPError, URLError

from collection import fetch_collection, write_json_atomic
from cosmo import fetch_public_account


OUTPUT_PATH = Path(__file__).resolve().parent / "web" / "public" / "data" / "collection.json"


def main() -> int:
    try:
        username = input("COSMO 暱稱：").strip().removeprefix("@")
        if not username:
            raise ValueError("請輸入 COSMO 暱稱。")
        account = fetch_public_account(username)
        print(f"公開帳號：{account['nickname']}，錢包：{account['address']}", flush=True)
        print("開始查詢同一區塊的完整持有清單，再取得官方卡片資料。", flush=True)
        snapshot = fetch_collection(account, progress=lambda message: print(message, flush=True))
        write_json_atomic(OUTPUT_PATH, snapshot)
    except (HTTPError, URLError, OSError, ValueError) as error:
        print(f"同步失敗：{error}", flush=True)
        print("未取代之前的完整收藏資料。", flush=True)
        return 1

    print(f"完整同步成功：{snapshot['total']} 張、{snapshot['unique_collections']} 款。", flush=True)
    print(f"Abstract 區塊：{snapshot['block_number']}；Token ID 全部不同。", flush=True)
    print(f"匯出檔案：{OUTPUT_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
