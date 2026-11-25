"""透過 Abstract 公開 RPC，唯讀列出同一區塊的 Objekt 持有清單。"""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from upstream import UpstreamBusyError, retry_read


RPC_URL = "https://api.mainnet.abs.xyz"
CHAIN_ID = 2741
CONTRACT_ADDRESS = "0x99bb83ae9bb0c0a6be865cacf67760947f91cb70"
MULTICALL_ADDRESS = "0xaa4de41dba0ca5dcbb288b7cc6b708f3aac759e7"
BATCH_SIZE = 200
RPC_WORKERS = 2
FALLBACK_BATCH_SIZE = 50


class SnapshotBlockChangedError(ValueError):
    pass


def rpc_batch(calls: list) -> list:
    """JSON-RPC 回應可以不同順序，必須依 id 還原並檢查每一筆。"""
    requests = [
        {"jsonrpc": "2.0", "id": index, "method": method, "params": params}
        for index, (method, params) in enumerate(calls, start=1)
    ]
    request = Request(
        RPC_URL,
        data=json.dumps(requests).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "COSMO-Collector-Copilot/0.1"},
    )
    with urlopen(request, timeout=25) as response:
        responses = json.load(response)
    # 有些節點會以單一錯誤物件拒絕整個批次。
    if isinstance(responses, dict) and "error" in responses:
        _raise_rpc_error(responses["error"])
    if not isinstance(responses, list) or len(responses) != len(requests):
        raise ValueError("RPC 批次回應筆數不完整。")

    by_id = {}
    for item in responses:
        if not isinstance(item, dict) or type(item.get("id")) is not int:
            raise ValueError("RPC 回應缺少有效的請求 id。")
        identifier = item["id"]
        if identifier in by_id:
            raise ValueError("RPC 回應的請求 id 重複。")
        if "error" in item:
            _raise_rpc_error(item["error"])
        if "result" not in item:
            raise ValueError("RPC 回應缺少查詢結果。")
        by_id[identifier] = item["result"]
    if set(by_id) != set(range(1, len(requests) + 1)):
        raise ValueError("RPC 回應的請求 id 與本次查詢不符。")
    return [by_id[index] for index in range(1, len(requests) + 1)]


def _raise_rpc_error(error) -> None:
    if isinstance(error, dict):
        message = str(error.get("message", "")).casefold()
        if error.get("code") in (429, -32005) or "rate limit" in message or "too many requests" in message:
            raise UpstreamBusyError("Abstract RPC 正在限制請求頻率。")
    raise ValueError(f"RPC 查詢失敗：{error}")


def _read_rpc(calls: list) -> list:
    return retry_read(lambda: rpc_batch(calls))


def decode_uint256(value: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}", value):
        raise ValueError("合約沒有回傳完整的 uint256 整數。")
    return int(value, 16)


def _contract_call(data: str, block: str, to: str = CONTRACT_ADDRESS) -> tuple:
    return "eth_call", [{"to": to, "data": data}, block]


def _aggregate_uint256(calldata: list[str], block: str) -> list[str]:
    """以 Multicall3 aggregate3 讀取一批只回傳 uint256 的 Objekt 呼叫。"""
    count = len(calldata)
    target = CONTRACT_ADDRESS[2:].zfill(64)
    # Call3 的欄位是 target、allowFailure=false、callData 的位置與長度。
    entries = []
    offsets = []
    next_offset = count * 32
    for data in calldata:
        padded_length = (len(data) + 63) // 64 * 64
        entry = target + f"{0:064x}{96:064x}{len(data) // 2:064x}" + data.ljust(padded_length, "0")
        offsets.append(f"{next_offset:064x}")
        entries.append(entry)
        next_offset += len(entry) // 2
    encoded = f"0x82ad56cb{32:064x}{count:064x}" + "".join(offsets + entries)
    result = _read_rpc([_contract_call(encoded, block, MULTICALL_ADDRESS)])[0]
    # Result[] 的每筆位置占 32 bytes，每筆結果是成功旗標、資料位置、長度與 uint256。
    if not isinstance(result, str) or not result.startswith("0x") or len(result) != 2 + 2 * (64 + 160 * count):
        raise ValueError("Multicall 回傳的持有清單筆數不完整。")
    raw = bytes.fromhex(result[2:])

    def word(offset):
        return int.from_bytes(raw[offset:offset + 32], "big")

    if len(raw) != 64 + 160 * count or word(0) != 32 or word(32) != count:
        raise ValueError("Multicall 回傳的持有清單格式不正確。")
    token_ids = []
    for index in range(count):
        offset = count * 32 + index * 128
        pos = 64 + offset
        if word(64 + index * 32) != offset or (word(pos), word(pos + 32), word(pos + 64)) != (1, 64, 32):
            raise ValueError("Multicall 的個別持有查詢失敗。")
        token_ids.append(str(word(pos + 96)))
    return token_ids


def _read_owner_batch(start: int, total: int, owner_parameter: str, block: str) -> list[str]:
    calldata = [
        "2f745c59" + owner_parameter + f"{index:064x}"
        for index in range(start, min(start + BATCH_SIZE, total))
    ]
    try:
        return _aggregate_uint256(calldata, block)
    except HTTPError as error:
        if error.code not in (400, 413, 422):
            raise
    except ValueError:
        # RPC 拒絕聚合呼叫或回傳格式錯誤時，仍可用原本的小批次唯讀查詢。
        pass

    tokens = []
    for offset in range(0, len(calldata), FALLBACK_BATCH_SIZE):
        calls = [_contract_call("0x" + data, block) for data in calldata[offset:offset + FALLBACK_BATCH_SIZE]]
        tokens.extend(str(decode_uint256(value)) for value in _read_rpc(calls))
    return tokens


def fetch_owned_tokens(address: str, progress=None) -> dict:
    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", address):
        raise ValueError("持有人錢包地址格式不正確。")

    network, block = _read_rpc([
        ("eth_chainId", []),
        ("eth_getBlockByNumber", ["latest", False]),
    ])
    if network != hex(CHAIN_ID):
        raise ValueError("RPC 所在網路不是預期的 Abstract 主網。")
    if not isinstance(block, dict) or not all(key in block for key in ("number", "hash", "timestamp")):
        raise ValueError("無法取得本次持有查詢的區塊資訊。")
    block_tag = block["number"]
    owner_parameter = address[2:].lower().zfill(64)
    balance_result = _read_rpc([_contract_call("0x70a08231" + owner_parameter, block_tag)])[0]
    total = decode_uint256(balance_result)

    token_ids = []
    if progress:
        progress(f"鏈上持有清單：0/{total:,}")
    if total:
        window_size = BATCH_SIZE * RPC_WORKERS
        with ThreadPoolExecutor(max_workers=RPC_WORKERS) as executor:
            for window in range(0, total, window_size):
                starts = range(window, min(window + window_size, total), BATCH_SIZE)
                batches = executor.map(lambda start: _read_owner_batch(start, total, owner_parameter, block_tag), starts)
                for batch in batches:
                    token_ids.extend(batch)
                    if progress:
                        progress(f"鏈上持有清單：{len(token_ids):,}/{total:,}")
    if len(token_ids) != total or len(set(token_ids)) != total:
        raise ValueError("持有清單筆數不符或 Token ID 重複，未接受此快照。")

    return {
        "token_ids": token_ids,
        "total": total,
        "chain_id": CHAIN_ID,
        "contract_address": CONTRACT_ADDRESS,
        "block_number": int(block_tag, 16),
        "block_hash": block["hash"],
        "block_timestamp": int(block["timestamp"], 16),
    }


def verify_snapshot_block(block_number: int, block_hash: str) -> None:
    block = _read_rpc([("eth_getBlockByNumber", [hex(block_number), False])])[0]
    if not isinstance(block, dict) or block.get("hash") != block_hash:
        raise SnapshotBlockChangedError("持有查詢的區塊已改變，請重新同步。")
