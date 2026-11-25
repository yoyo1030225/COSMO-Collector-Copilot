import copy
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from fastapi.testclient import TestClient

from api import create_app
from chain import SnapshotBlockChangedError
from collection import MissingMetadataError, write_json_atomic
from collection_jobs import CollectionBusyError, CollectionJobs


ACCOUNT = {"nickname": "example", "address": "0x" + "1" * 40}
SNAPSHOT = {
    "account": ACCOUNT, "complete": True, "total": 1, "unique_collections": 1,
    "objekts": [{"external_token_id": "123"}],
}


class CollectionJobsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.jobs = CollectionJobs(self.directory)

    def test_reuses_active_nickname_and_limits_other_simultaneous_queries(self):
        first, created = self.jobs.create("example")
        repeated, repeated_created = self.jobs.create("EXAMPLE")
        self.assertTrue(created)
        self.assertFalse(repeated_created)
        self.assertEqual(first["job_id"], repeated["job_id"])
        with self.assertRaises(CollectionBusyError):
            self.jobs.create("another")

    def test_success_reports_progress_and_saves_by_wallet(self):
        job, _ = self.jobs.create("example")

        def fetch(account, progress, on_tokens, on_card, get_priority):
            progress("鏈上持有清單：1/1")
            waiting = self.jobs.get(job["job_id"], cursor=0, include_tokens=True)
            self.assertEqual(waiting["account"], ACCOUNT)
            self.assertEqual(waiting["progress"], "鏈上持有清單：1/1")
            self.assertIsNone(waiting["token_ids"])
            on_tokens(["123"])
            on_card(SNAPSHOT["objekts"][0])
            return copy.deepcopy(SNAPSHOT)

        with patch("collection_jobs.fetch_public_account", return_value=ACCOUNT), patch("collection_jobs.fetch_collection", side_effect=fetch):
            self.jobs.run(job["job_id"])
        finished = self.jobs.get(job["job_id"])
        self.assertEqual(finished["status"], "succeeded")
        self.assertEqual(self.jobs.latest(), SNAPSHOT)
        self.assertTrue((self.directory / f"{ACCOUNT['address']}.json").exists())
        self.assertEqual(finished["snapshot"], SNAPSHOT)

    def test_incomplete_or_failed_queries_keep_previous_success(self):
        write_json_atomic(self.directory / "latest.json", SNAPSHOT)
        for snapshot in ({**SNAPSHOT, "complete": False}, {**SNAPSHOT, "total": 2}):
            with self.subTest(snapshot=snapshot):
                job, _ = self.jobs.create("example")
                with patch("collection_jobs.fetch_public_account", return_value=ACCOUNT), patch("collection_jobs.fetch_collection", return_value=snapshot):
                    self.jobs.run(job["job_id"])
                self.assertEqual(self.jobs.get(job["job_id"])["status"], "failed")
                self.assertEqual(self.jobs.latest(), SNAPSHOT)

    def test_missing_nickname_returns_a_clear_error_and_releases_the_slot(self):
        job, _ = self.jobs.create("missing")
        with patch("collection_jobs.fetch_public_account", side_effect=HTTPError("https://example.com", 404, "not found", {}, None)):
            self.jobs.run(job["job_id"])
        self.assertIn("找不到 COSMO 暱稱", self.jobs.get(job["job_id"])["error"])
        self.assertEqual(self.jobs.get(job["job_id"])["status"], "failed")
        self.jobs.create("next-user")

    def test_exposes_verified_ids_when_metadata_is_missing_but_withdraws_changed_block(self):
        write_json_atomic(self.directory / "latest.json", SNAPSHOT)
        for error, expected in ((MissingMetadataError(1, []), ("123", "124")), (SnapshotBlockChangedError("reorg"), None)):
            with self.subTest(error=error):
                job, _ = self.jobs.create("example")

                def fetch(account, progress, on_tokens, on_card, get_priority):
                    on_tokens(["123", "124"])
                    on_card(SNAPSHOT["objekts"][0])
                    raise error

                with patch("collection_jobs.fetch_public_account", return_value=ACCOUNT), patch("collection_jobs.fetch_collection", side_effect=fetch):
                    self.jobs.run(job["job_id"])
                state = self.jobs.get(job["job_id"], cursor=0, include_tokens=True)
                self.assertEqual(state["status"], "failed")
                self.assertEqual(state["token_ids"], expected)
                self.assertEqual(state["cards"], SNAPSHOT["objekts"] if expected else [])
                self.assertIsNone(state["result"])
                self.assertEqual(self.jobs.latest(), SNAPSHOT)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.jobs = CollectionJobs(Path(self.temporary.name))
        self.client = TestClient(create_app(self.jobs))
        self.addCleanup(self.client.close)

    def test_rejects_empty_invalid_and_oversized_input_before_querying(self):
        for nickname in ("", "   ", "@", "a" * 65, "abc\ndef", 123):
            with self.subTest(nickname=nickname):
                response = self.client.post("/collections/sync", json={"nickname": nickname})
                self.assertEqual(response.status_code, 422)

    def test_post_normalizes_nickname_and_status_returns_the_completed_snapshot(self):
        with patch("collection_jobs.fetch_public_account", return_value=ACCOUNT) as account, patch("collection_jobs.fetch_collection", return_value=SNAPSHOT):
            response = self.client.post("/collections/sync", json={"nickname": " @example "})
        self.assertEqual(response.status_code, 202)
        account.assert_called_once_with("example")
        status = self.client.get("/collections/jobs/" + response.json()["job_id"])
        self.assertEqual(status.json()["status"], "succeeded")
        self.assertEqual(status.json()["snapshot"], SNAPSHOT)
        self.assertEqual(status.headers["cache-control"], "no-store")
        self.assertEqual(self.client.get("/collections/latest").json(), SNAPSHOT)

    def test_missing_job_and_saved_snapshot_return_404(self):
        self.assertEqual(self.client.get("/collections/jobs/" + "0" * 32).status_code, 404)
        self.assertEqual(self.client.get("/collections/latest").status_code, 404)

    def test_large_collection_is_transferred_in_limited_updates_without_missing_entries(self):
        ids = list(map(str, range(10001, 0, -1)))
        records = [{"external_token_id": identifier} for identifier in ids]

        def fetch(account, progress, on_tokens, on_card, get_priority):
            on_tokens(ids)
            for card in records:
                on_card(card)
            return {**SNAPSHOT, "total": len(records), "objekts": records}

        with patch("collection_jobs.fetch_public_account", return_value=ACCOUNT), patch("collection_jobs.fetch_collection", side_effect=fetch):
            created = self.client.post("/collections/sync", json={"nickname": "example"})
        url = "/collections/jobs/" + created.json()["job_id"]
        cursor = 0
        downloaded = []
        while True:
            response = self.client.get(url, params={"cursor": cursor, "include_tokens": cursor == 0})
            self.assertEqual(response.status_code, 200)
            update = response.json()
            self.assertNotIn("snapshot", update)
            self.assertNotIn("objekts", update["result"])
            self.assertEqual(update["token_ids"], ids if cursor == 0 else None)
            self.assertLessEqual(len(update["cards"]), 300)
            downloaded.extend(update["cards"])
            self.assertEqual(update["next_cursor"], len(downloaded))
            if not update["has_more"]:
                break
            self.assertGreater(update["next_cursor"], cursor)
            cursor = update["next_cursor"]
        self.assertEqual(downloaded, records)
        self.assertEqual(update["result"]["total"], 10001)

    def test_other_active_query_returns_409(self):
        self.jobs.create("first")
        self.assertEqual(self.client.post("/collections/sync", json={"nickname": "second"}).status_code, 409)

    def test_accepts_only_verified_tokens_when_prioritizing_the_current_page(self):
        job, _ = self.jobs.create("example")
        job_id = job["job_id"]
        url = f"/collections/jobs/{job_id}/prioritize"

        def fetch(account, progress, on_tokens, on_card, get_priority):
            self.assertEqual(self.client.post(url, json={"token_ids": ["123"]}).status_code, 204)
            self.assertEqual(get_priority(), ())
            on_tokens(["123", "124"])
            self.assertEqual(self.client.post(url, json={"token_ids": ["124", "999", "123"]}).status_code, 204)
            self.assertEqual(get_priority(), ("124", "123"))
            self.assertEqual(self.client.post(url, json={"token_ids": ["123"]}).status_code, 204)
            self.assertEqual(get_priority(), ("123",))
            self.assertEqual(self.client.post(url, json={"token_ids": []}).status_code, 204)
            self.assertEqual(get_priority(), ())
            records = [{"external_token_id": token} for token in ("123", "124")]
            for record in records:
                on_card(record)
            return {**SNAPSHOT, "total": len(records), "objekts": records}

        with patch("collection_jobs.fetch_public_account", return_value=ACCOUNT), patch(
            "collection_jobs.fetch_collection", side_effect=fetch,
        ):
            self.jobs.run(job_id)
        self.assertEqual(self.jobs.get(job_id)["status"], "succeeded")
        self.assertEqual(self.client.post("/collections/jobs/" + "0" * 32 + "/prioritize", json={"token_ids": []}).status_code, 404)
        for ids in ([123], ["-1"], ["1\n"], ["1" * 79], ["1"] * 61):
            with self.subTest(ids=ids):
                self.assertEqual(self.client.post(url, json={"token_ids": ids}).status_code, 422)


class AtomicWriteTests(unittest.TestCase):
    def test_simultaneous_writers_leave_one_complete_file_without_temporary_files(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "snapshot.json"
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda index: write_json_atomic(path, {"writer": index, "cards": list(range(1000))}), range(12)))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["cards"], list(range(1000)))
            self.assertEqual([file.name for file in Path(folder).iterdir()], ["snapshot.json"])
