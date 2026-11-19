import io
import json
import unittest
from unittest.mock import patch

from chain import decode_uint256, fetch_owned_tokens, rpc_batch, verify_snapshot_block


ADDRESS = "0x" + "1" * 40
BLOCK = {"number": "0x64", "hash": "0x" + "2" * 64, "timestamp": "0x6553f100"}


def encoded(value):
    return "0x" + f"{value:064x}"


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
        self.assertEqual(decode_uint256(encoded(719)), 719)
        for value in ("0x", "0x01", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    decode_uint256(value)


class OwnedTokensTests(unittest.TestCase):
    def test_every_enumeration_call_uses_the_same_block(self):
        with patch("chain.BATCH_SIZE", 2), patch("chain.rpc_batch", side_effect=[
            ["0xab5", BLOCK], [encoded(3)], [encoded(9), encoded(10)], [encoded(11)],
        ]) as batch:
            snapshot = fetch_owned_tokens(ADDRESS)

        self.assertEqual(snapshot["token_ids"], ["9", "10", "11"])
        self.assertEqual(snapshot["total"], 3)
        self.assertEqual(snapshot["block_number"], 100)
        calls = [call for invocation in batch.call_args_list[1:] for call in invocation.args[0]]
        self.assertTrue(all(params[-1] == "0x64" for _, params in calls))
        self.assertEqual(len(calls), 4)  # 一次 balanceOf，加上三張個別卡片。

    def test_duplicate_tokens_never_become_a_complete_collection(self):
        with patch("chain.rpc_batch", side_effect=[
            ["0xab5", BLOCK], [encoded(2)], [encoded(9), encoded(9)],
        ]):
            with self.assertRaisesRegex(ValueError, "Token ID 重複"):
                fetch_owned_tokens(ADDRESS)

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
