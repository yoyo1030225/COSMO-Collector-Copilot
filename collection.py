"""將完整鏈上持有清單與官方 metadata 合成可供網頁讀取的快照。"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError

from chain import CHAIN_ID, CONTRACT_ADDRESS, RPC_URL, fetch_owned_tokens, verify_snapshot_block
from cosmo import BASE_URL, fetch_objekt_metadata, normalize_objekt_metadata


METADATA_WORKERS = 4
CACHE_MAX_AGE_SECONDS = 24 * 60 * 60
DEFAULT_CACHE = Path(__file__).resolve().parent / "data" / "cosmo-metadata" / str(CHAIN_ID) / CONTRACT_ADDRESS


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        for attempt in range(5):
            try:
                temporary.replace(path)
                break
            except PermissionError:
                # Windows 可能短暫鎖住替換目標；僅有限重試，失敗仍保留原檔。
                if attempt == 4:
                    raise
                time.sleep(0.02 * (attempt + 1))
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _fetch_card(token_id: str, cache_directory: Path) -> dict:
    cache_path = cache_directory / f"{token_id}.json"
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        age = time.time() - cached["fetched_at"]
        if cached["token_id"] == token_id and 0 <= age < CACHE_MAX_AGE_SECONDS:
            return normalize_objekt_metadata(token_id, cached["metadata"])
    except (OSError, ValueError, KeyError, TypeError):
        pass

    for attempt in range(3):
        try:
            raw = fetch_objekt_metadata(token_id)
            card = normalize_objekt_metadata(token_id, raw)
            write_json_atomic(cache_path, {"token_id": token_id, "fetched_at": time.time(), "metadata": raw})
            return card
        except HTTPError as error:
            if error.code not in (404, 408, 429, 500, 502, 503, 504) or attempt == 2:
                raise
            retry_after = error.headers.get("Retry-After", "") if error.headers else ""
            delay = min(int(retry_after), 30) if retry_after.isdigit() else 2 ** (attempt + 1)
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
            delay = 2 ** (attempt + 1)
        time.sleep(delay)
    raise ValueError(f"無法取得 Token ID {token_id} 的基本資料。")


def fetch_collection(account: dict, progress=None, cache_directory: Path = DEFAULT_CACHE) -> dict:
    ownership = fetch_owned_tokens(account["address"], progress)
    token_ids = ownership["token_ids"]
    cards = {}
    failures = []
    with ThreadPoolExecutor(max_workers=METADATA_WORKERS) as executor:
        futures = {executor.submit(_fetch_card, token_id, cache_directory): token_id for token_id in token_ids}
        for future in as_completed(futures):
            token_id = futures[future]
            try:
                cards[token_id] = future.result()
            except (HTTPError, URLError, OSError, ValueError) as error:
                failures.append(f"{token_id} ({error})")
            completed = len(cards) + len(failures)
            if progress and (completed % 25 == 0 or completed == len(token_ids)):
                progress(f"卡片基本資料：{completed}/{len(token_ids)}，失敗 {len(failures)}")
    if failures:
        raise ValueError(f"{len(failures)} 張卡片資料取得失敗，未取代原快照：" + "; ".join(failures[:3]))

    verify_snapshot_block(ownership["block_number"], ownership["block_hash"])
    ordered = [cards[token_id] for token_id in sorted(token_ids, key=int, reverse=True)]
    definitions = {(card["artist"], card["season"], card["member"], card["collection_code"]) for card in ordered}
    return {
        "account": account,
        "complete": True,
        "total": ownership["total"],
        "unique_collections": len(definitions),
        "objekts": ordered,
        "chain_id": ownership["chain_id"],
        "chain_name": "Abstract",
        "contract_address": ownership["contract_address"],
        "block_number": ownership["block_number"],
        "block_hash": ownership["block_hash"],
        "ownership_at": datetime.fromtimestamp(ownership["block_timestamp"], timezone.utc).isoformat(timespec="seconds"),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ownership_source": RPC_URL,
        "metadata_source": BASE_URL,
    }
