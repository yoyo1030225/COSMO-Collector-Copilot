"""透過 Abstract 公開 RPC，唯讀列出同一區塊的 Objekt 持有清單。"""

import json
import re
from urllib.request import Request, urlopen


RPC_URL = "https://api.mainnet.abs.xyz"
CHAIN_ID = 2741
CONTRACT_ADDRESS = "0x99bb83ae9bb0c0a6be865cacf67760947f91cb70"
BATCH_SIZE = 50
MAX_TOKEN_COUNT = 10000


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
            raise ValueError(f"RPC 查詢失敗：{item['error']}")
        if "result" not in item:
            raise ValueError("RPC 回應缺少查詢結果。")
        by_id[identifier] = item["result"]
    if set(by_id) != set(range(1, len(requests) + 1)):
        raise ValueError("RPC 回應的請求 id 與本次查詢不符。")
    return [by_id[index] for index in range(1, len(requests) + 1)]


def decode_uint256(value: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}", value):
        raise ValueError("合約沒有回傳完整的 uint256 整數。")
    return int(value, 16)


def _contract_call(data: str, block: str) -> tuple:
    return "eth_call", [{"to": CONTRACT_ADDRESS, "data": data}, block]


def fetch_owned_tokens(address: str, progress=None) -> dict:
    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", address):
        raise ValueError("持有人錢包地址格式不正確。")

    network, block = rpc_batch([
        ("eth_chainId", []),
        ("eth_getBlockByNumber", ["latest", False]),
    ])
    if network != hex(CHAIN_ID):
        raise ValueError("RPC 所在網路不是預期的 Abstract 主網。")
    if not isinstance(block, dict) or not all(key in block for key in ("number", "hash", "timestamp")):
        raise ValueError("無法取得本次持有查詢的區塊資訊。")
    block_tag = block["number"]
    owner_parameter = address[2:].lower().zfill(64)
    balance_result = rpc_batch([_contract_call("0x70a08231" + owner_parameter, block_tag)])[0]
    total = decode_uint256(balance_result)
    if total > MAX_TOKEN_COUNT:
        raise ValueError(f"本範例最多支援 {MAX_TOKEN_COUNT} 張；未輸出部分持有清單。")

    token_ids = []
    for start in range(0, total, BATCH_SIZE):
        calls = [
            _contract_call("0x2f745c59" + owner_parameter + f"{index:064x}", block_tag)
            for index in range(start, min(start + BATCH_SIZE, total))
        ]
        token_ids.extend(str(decode_uint256(value)) for value in rpc_batch(calls))
        if progress:
            progress(f"鏈上持有清單：{len(token_ids)}/{total}")
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
    block = rpc_batch([("eth_getBlockByNumber", [hex(block_number), False])])[0]
    if not isinstance(block, dict) or block.get("hash") != block_hash:
        raise ValueError("持有查詢的區塊已改變，請重新同步；保留之前的完整快照。")
