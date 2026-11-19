import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collection import _fetch_card, fetch_collection
import sync_collection


ACCOUNT = {"nickname": "example", "address": "0x" + "1" * 40}
OWNERSHIP = {
    "token_ids": ["9", "10"], "total": 2, "chain_id": 2741,
    "contract_address": "0x99bb83ae9bb0c0a6be865cacf67760947f91cb70",
    "block_number": 100, "block_hash": "0x" + "2" * 64, "block_timestamp": 1700000000,
}


def card(token_id, _cache):
    return {
        "external_token_id": token_id, "name": "Cream02 Kotone 114Z", "artist": "tripleS",
        "member": "Kotone", "members": ["Kotone"], "season": "Cream02",
        "collection_code": "114Z", "class_name": "First", "image_url": "https://example.com/image.webp",
    }


class CollectionTests(unittest.TestCase):
    def test_keeps_distinct_copies_and_checks_block_before_completing(self):
        with patch("collection.fetch_owned_tokens", return_value=OWNERSHIP), patch(
            "collection._fetch_card", side_effect=card,
        ), patch("collection.verify_snapshot_block") as verify:
            snapshot = fetch_collection(ACCOUNT)

        self.assertIs(snapshot["complete"], True)
        self.assertEqual(snapshot["total"], 2)
        self.assertEqual(snapshot["unique_collections"], 1)
        self.assertEqual([item["external_token_id"] for item in snapshot["objekts"]], ["10", "9"])
        verify.assert_called_once_with(100, OWNERSHIP["block_hash"])

    def test_a_metadata_failure_does_not_return_a_partial_snapshot(self):
        def fail_one(token_id, cache):
            if token_id == "10":
                raise ValueError("unavailable")
            return card(token_id, cache)

        with patch("collection.fetch_owned_tokens", return_value=OWNERSHIP), patch(
            "collection._fetch_card", side_effect=fail_one,
        ):
            with self.assertRaisesRegex(ValueError, "未取代原快照"):
                fetch_collection(ACCOUNT)

    def test_cli_keeps_the_previous_file_when_sync_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "collection.json"
            output.write_text('{"previous":"complete"}', encoding="utf-8")
            with patch.object(sync_collection, "OUTPUT_PATH", output), patch(
                "sync_collection.fetch_public_account", return_value=ACCOUNT,
            ), patch("sync_collection.fetch_collection", side_effect=ValueError("request failed")), patch("builtins.print"):
                self.assertEqual(sync_collection.main(), 1)
            self.assertEqual(output.read_text(encoding="utf-8"), '{"previous":"complete"}')

    def test_valid_metadata_cache_avoids_another_official_request(self):
        raw = {
            "name": "Cream02 Kotone 114Z", "image": "https://example.com/image.webp",
            "attributes": [{"trait_type": key, "value": value} for key, value in (
                ("Artist", "tripleS"), ("Member", "Kotone"), ("Season", "Cream02"),
                ("Collection", "114Z"), ("Class", "First"),
            )],
        }
        with tempfile.TemporaryDirectory() as folder, patch("collection.fetch_objekt_metadata", return_value=raw) as fetch:
            directory = Path(folder)
            first = _fetch_card("9", directory)
            second = _fetch_card("9", directory)
            self.assertEqual(first, second)
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(json.loads((directory / "9.json").read_text(encoding="utf-8"))["token_id"], "9")
