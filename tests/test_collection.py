import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from collection import _fetch_card, fetch_collection
import sync_collection
from upstream import RateLimitCooldown, retry_read


ACCOUNT = {"nickname": "example", "address": "0x" + "1" * 40}
OWNERSHIP = {
    "token_ids": ["9", "10"], "total": 2, "chain_id": 2741,
    "contract_address": "0x99bb83ae9bb0c0a6be865cacf67760947f91cb70",
    "block_number": 100, "block_hash": "0x" + "2" * 64, "block_timestamp": 1700000000,
}


def card(token_id, _cache, _connection=None, *, cooldown=None):
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
        def fail_one(token_id, cache, connection=None, *, cooldown=None):
            if token_id == "10":
                raise ValueError("unavailable")
            return card(token_id, cache, connection)

        verified = []
        ready = []

        with patch("collection.fetch_owned_tokens", return_value=OWNERSHIP), patch(
            "collection._fetch_card", side_effect=fail_one,
        ), patch("collection.verify_snapshot_block"):
            with self.assertRaisesRegex(ValueError, "未取代原快照"):
                fetch_collection(ACCOUNT, on_tokens=verified.extend, on_card=ready.append)

        self.assertEqual(verified, ["10", "9"])
        self.assertEqual([card["external_token_id"] for card in ready], ["9"])

    def test_fetches_the_requested_last_page_before_the_rest_of_a_large_collection(self):
        token_ids = list(map(str, range(10001, 0, -1)))
        last_page = token_ids[9960:]
        completed = []

        with patch("collection.METADATA_WORKERS", 1), patch("collection.fetch_owned_tokens", return_value={
            **OWNERSHIP, "token_ids": token_ids, "total": len(token_ids),
        }), patch("collection._fetch_card", side_effect=card), patch("collection.verify_snapshot_block"):
            snapshot = fetch_collection(
                ACCOUNT,
                on_card=lambda item: completed.append(item["external_token_id"]),
                get_priority=lambda: last_page if completed else (),
            )

        self.assertEqual(completed[:42], [token_ids[0], *last_page])
        self.assertCountEqual(completed, token_ids)
        self.assertEqual([item["external_token_id"] for item in snapshot["objekts"]], token_ids)

    def test_cli_keeps_the_previous_file_when_sync_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "collection.json"
            output.write_text('{"previous":"complete"}', encoding="utf-8")
            with patch.object(sync_collection, "OUTPUT_PATH", output), patch(
                "sync_collection.fetch_public_account", return_value=ACCOUNT,
            ) as fetch_account, patch("builtins.input", return_value=" @example "), patch(
                "sync_collection.fetch_collection", side_effect=ValueError("request failed"),
            ), patch("builtins.print"):
                self.assertEqual(sync_collection.main(), 1)
            fetch_account.assert_called_once_with("example")
            self.assertEqual(output.read_text(encoding="utf-8"), '{"previous":"complete"}')

    def test_cli_rejects_empty_input_without_querying_an_account(self):
        with patch("builtins.input", return_value="   "), patch(
            "sync_collection.fetch_public_account",
        ) as fetch_account, patch("builtins.print"):
            self.assertEqual(sync_collection.main(), 1)
        fetch_account.assert_not_called()

    def test_valid_metadata_cache_avoids_another_official_request(self):
        raw = {
            "name": "Cream02 Kotone 114Z", "image": "https://example.com/image.webp",
            "attributes": [{"trait_type": key, "value": value} for key, value in (
                ("Artist", "tripleS"), ("Member", "Kotone"), ("Season", "Cream02"),
                ("Collection", "114Z"), ("Class", "First"),
            )],
        }
        with tempfile.TemporaryDirectory() as folder, patch("collection.fetch_objekt_metadata", return_value=raw) as fetch, patch(
            "collection.time.time", return_value=100_000,
        ) as clock:
            directory = Path(folder)
            first = _fetch_card("9", directory)
            clock.return_value += 2 * 24 * 60 * 60
            second = _fetch_card("9", directory)
            self.assertEqual(first, second)
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(json.loads((directory / "9.json").read_text(encoding="utf-8"))["token_id"], "9")
            clock.return_value += 5 * 24 * 60 * 60
            self.assertEqual(_fetch_card("9", directory), first)
            self.assertEqual(fetch.call_count, 2)

    def test_rate_limit_cooldown_applies_to_other_metadata_reads(self):
        cooldown = RateLimitCooldown()
        attempts = []

        def throttled():
            attempts.append("limited")
            raise HTTPError("https://example.invalid/metadata", 429, "rate limit", {"Retry-After": "5"}, None)

        with patch("upstream.time.monotonic", return_value=0) as clock:
            def advance(seconds):
                clock.return_value += seconds

            with patch("upstream.time.sleep", side_effect=advance) as sleep:
                with self.assertRaises(HTTPError):
                    retry_read(throttled, cooldown=cooldown)
                self.assertEqual(len(attempts), 3)
                self.assertEqual(clock.return_value, 10)
                request_started = retry_read(lambda: clock.return_value, cooldown=cooldown)
                self.assertEqual(request_started, 15)
                self.assertEqual([call.args[0] for call in sleep.call_args_list], [5, 5, 5])
