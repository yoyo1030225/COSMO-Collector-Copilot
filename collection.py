"""將完整鏈上持有清單與官方 metadata 合成可供網頁讀取的快照。"""

import json
import logging
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from tempfile import NamedTemporaryFile

from chain import CHAIN_ID, CONTRACT_ADDRESS, RPC_URL, fetch_owned_tokens, verify_snapshot_block
from cosmo import BASE_URL, fetch_objekt_metadata, normalize_objekt_metadata, open_metadata_connection
from upstream import RateLimitCooldown, retry_read


METADATA_WORKERS = 8
CACHE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
DEFAULT_CACHE = Path(__file__).resolve().parent / "data" / "cosmo-metadata" / str(CHAIN_ID) / CONTRACT_ADDRESS
logger = logging.getLogger(__name__)


class MissingMetadataError(ValueError):
    def __init__(self, count: int, examples: list[str]):
        super().__init__(f"{count} 張卡片資料取得失敗，未取代原快照：" + "; ".join(examples))
        self.count = count


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


def _fetch_card(token_id: str, cache_directory: Path, connection=None, *, cooldown=None) -> dict:
    cache_path = cache_directory / f"{token_id}.json"
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        age = time.time() - cached["fetched_at"]
        if cached["token_id"] == token_id and 0 <= age < CACHE_MAX_AGE_SECONDS:
            return normalize_objekt_metadata(token_id, cached["metadata"])
    except (OSError, ValueError, KeyError, TypeError):
        pass

    raw = retry_read(
        lambda: fetch_objekt_metadata(token_id, connection),
        retry_not_found=True, cooldown=cooldown,
    )
    card = normalize_objekt_metadata(token_id, raw)
    try:
        write_json_atomic(cache_path, {"token_id": token_id, "fetched_at": time.time(), "metadata": raw})
    except OSError:
        # 已收到有效資料，寫不進可重建的快取不應讓卡片消失。
        logger.debug("Unable to write metadata cache", exc_info=True)
    return card


def _read_cards(token_ids: list[str], cache_directory: Path, progress, on_card, get_priority) -> dict:
    cards = {}
    failures = 0
    examples = []
    if not token_ids:
        return cards

    cooldown = RateLimitCooldown()
    with ExitStack() as stack:
        connections = Queue()
        for _ in range(METADATA_WORKERS):
            connection = open_metadata_connection()
            if connection is not None:
                stack.callback(connection.close)
            connections.put(connection)

        def read(token_id):
            connection = connections.get_nowait()
            try:
                return _fetch_card(token_id, cache_directory, connection, cooldown=cooldown)
            finally:
                connections.put(connection)

        executor = stack.enter_context(ThreadPoolExecutor(max_workers=METADATA_WORKERS))
        remaining = iter(token_ids)
        unscheduled = set(token_ids)
        futures = {}

        def schedule_next():
            if not unscheduled:
                return
            priority = get_priority() if get_priority else ()
            token_id = next((token for token in priority if token in unscheduled), None)
            if token_id is None:
                token_id = next(token for token in remaining if token in unscheduled)
            unscheduled.remove(token_id)
            futures[executor.submit(read, token_id)] = token_id

        # 只排入能立刻執行的工作，翻頁時下一個空位就能換成新頁面的卡片。
        for _ in range(METADATA_WORKERS):
            schedule_next()
        while futures:
            finished, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in finished:
                token_id = futures.pop(future)
                try:
                    card = future.result()
                except (OSError, ValueError) as error:
                    failures += 1
                    if len(examples) < 3:
                        examples.append(f"{token_id} ({error})")
                else:
                    cards[token_id] = card
                    if on_card:
                        on_card(card)

                completed = len(cards) + failures
                if progress and (completed % 25 == 0 or completed == len(token_ids)):
                    progress(f"卡片資料：{len(cards):,}/{len(token_ids):,}，未取得 {failures:,}")
                schedule_next()

    if failures:
        raise MissingMetadataError(failures, examples)
    return cards


def fetch_collection(
    account: dict, progress=None, cache_directory: Path = DEFAULT_CACHE, *, on_tokens=None, on_card=None, get_priority=None,
) -> dict:
    ownership = fetch_owned_tokens(account["address"], progress)
    token_ids = sorted(ownership["token_ids"], key=int, reverse=True)
    if on_tokens:
        verify_snapshot_block(ownership["block_number"], ownership["block_hash"])
        on_tokens(token_ids)
    try:
        cards = _read_cards(token_ids, cache_directory, progress, on_card, get_priority)
    except MissingMetadataError:
        if on_tokens:
            verify_snapshot_block(ownership["block_number"], ownership["block_hash"])
        raise
    verify_snapshot_block(ownership["block_number"], ownership["block_hash"])
    ordered = [cards[token_id] for token_id in token_ids]
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
