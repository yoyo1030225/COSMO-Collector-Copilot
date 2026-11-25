import io
import json
import unittest
from unittest.mock import patch

from chain import BATCH_SIZE, MULTICALL_ADDRESS, decode_uint256, fetch_owned_tokens, rpc_batch, verify_snapshot_block


ADDRESS = "0x" + "1" * 40
BLOCK = {"number": "0x64", "hash": "0x" + "2" * 64, "timestamp": "0x6553f100"}


def encoded(value):
    return "0x" + f"{value:064x}"


def multicall_reply(values):
    count = len(values)
    heads = [count * 32 + index * 128 for index in range(count)]
    results = [value for result in values for value in (1, 64, 32, result)]
    return "0x" + "".join(f"{word:064x}" for word in [32, count, *heads, *results])


def requested_indices(encoded_call):
    data = bytes.fromhex(encoded_call[10:])
    count = int.from_bytes(data[32:64], "big")
    indices = []
    for start in range(64, 64 + count * 32, 32):
        call = 64 + int.from_bytes(data[start:start + 32], "big") + 128
        assert data[call:call + 4].hex() == "2f745c59"
        indices.append(int.from_bytes(data[call + 36:call + 68], "big"))
    return indices


class RpcTests(unittest.TestCase):
    def test_reorders_batch_results_by_request_id(self):
        body = [{"id": 2, "result": "second"}, {"id": 1, "result": "first"}]
        with patch("chain.urlopen", return_value=io.BytesIO(json.dumps(body).encode())):
            result = rpc_batch([("first", []), ("second", [])])
        self.assertEqual(result, ["first", "second"])

    def test_rejects_missing_duplicate_error_and_mismatched_responses(self):
        for body in (
            [{"id": 1, "result": "a"}],
            [{"id": 1, "result": "a"}, {"id": 1, "result": "b"}],
            [{"id": 1, "error": {"message": "failed"}}, {"id": 2, "result": "b"}],
            [{"id": 1, "result": "a"}, {"id": 3, "result": "b"}],
        ):
            with self.subTest(body=body):
                with patch("chain.urlopen", return_value=io.BytesIO(json.dumps(body).encode())):
                    with self.assertRaises(ValueError):
                        rpc_batch([("first", []), ("second", [])])

    def test_uint_rejects_empty_or_truncated_contract_results(self):
        self.assertEqual(decode_uint256(encoded(42)), 42)
        for value in ("0x", "0x01", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    decode_uint256(value)


class OwnedTokensTests(unittest.TestCase):
    def test_enumerates_more_than_ten_thousand_tokens_without_truncating(self):
        total = 10001

        def rpc(calls):
            if calls[0][0] == "eth_chainId":
                return ["0xab5", BLOCK]
            if calls[0][1][0]["data"].startswith("0x70a08231"):
                return [encoded(total)]
            [(method, [call, block])] = calls
            self.assertEqual(method, "eth_call")
            self.assertEqual(call["to"], MULTICALL_ADDRESS)
            self.assertEqual(block, BLOCK["number"])
            indices = requested_indices(call["data"])
            self.assertLessEqual(len(indices), BATCH_SIZE)
            return [multicall_reply([index + 1 for index in indices])]

        with patch("chain.rpc_batch", side_effect=rpc) as batch:
            snapshot = fetch_owned_tokens(ADDRESS)

        self.assertEqual(snapshot["total"], total)
        self.assertEqual(len(snapshot["token_ids"]), total)
        self.assertEqual(len(set(snapshot["token_ids"])), total)
        self.assertEqual(snapshot["token_ids"][0], "1")
        self.assertEqual(snapshot["token_ids"][-1], str(total))
        self.assertEqual(batch.call_count, 53)  # 網路與區塊、張數，再加 51 批持有查詢。

    def test_every_enumeration_call_uses_the_same_block(self):
        with patch("chain.BATCH_SIZE", 2), patch("chain.RPC_WORKERS", 1), patch("chain.rpc_batch", side_effect=[
            ["0xab5", BLOCK], [encoded(3)], [multicall_reply([9, 10])], [multicall_reply([11])],
        ]) as batch:
            snapshot = fetch_owned_tokens(ADDRESS)

        self.assertEqual(snapshot["token_ids"], ["9", "10", "11"])
        self.assertEqual(snapshot["total"], 3)
        self.assertEqual(snapshot["block_number"], 100)
        calls = [call for invocation in batch.call_args_list[1:] for call in invocation.args[0]]
        self.assertTrue(all(params[-1] == "0x64" for _, params in calls))
        self.assertEqual(len(calls), 3)  # 一次 balanceOf，加上兩批聚合查詢。

    def test_duplicate_tokens_never_become_a_complete_collection(self):
        with patch("chain.rpc_batch", side_effect=[
            ["0xab5", BLOCK], [encoded(2)], [multicall_reply([9, 9])],
        ]):
            with self.assertRaisesRegex(ValueError, "Token ID 重複"):
                fetch_owned_tokens(ADDRESS)

    def test_retries_throttling_then_uses_direct_reads_if_aggregation_is_rejected(self):
        from upstream import UpstreamBusyError

        with patch("upstream.time.sleep"), patch("chain.rpc_batch", side_effect=[
            ["0xab5", BLOCK], [encoded(2)], UpstreamBusyError("busy"), ValueError("multicall rejected"),
            [encoded(9), encoded(10)],
        ]) as batch:
            snapshot = fetch_owned_tokens(ADDRESS)

        self.assertEqual(snapshot["token_ids"], ["9", "10"])
        self.assertEqual(batch.call_args_list[2], batch.call_args_list[3])
        direct = batch.call_args.args[0]
        self.assertTrue(all(params[0]["data"].startswith("0x2f745c59") and params[-1] == BLOCK["number"] for _, params in direct))

    def test_accepts_a_confirmed_zero_balance(self):
        with patch("chain.rpc_batch", side_effect=[["0xab5", BLOCK], [encoded(0)]]):
            snapshot = fetch_owned_tokens(ADDRESS)
        self.assertEqual(snapshot["token_ids"], [])
        self.assertEqual(snapshot["total"], 0)

    def test_rejects_the_wrong_network_and_changed_block(self):
        with patch("chain.rpc_batch", return_value=["0x1", BLOCK]):
            with self.assertRaisesRegex(ValueError, "不是預期"):
                fetch_owned_tokens(ADDRESS)
        with patch("chain.rpc_batch", return_value=[{**BLOCK, "hash": "0x" + "3" * 64}]):
            with self.assertRaisesRegex(ValueError, "區塊已改變"):
                verify_snapshot_block(100, BLOCK["hash"])
