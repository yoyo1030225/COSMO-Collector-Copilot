"""本機收藏查詢工作：回報進度、保留成功快照，同時只執行一個查詢。"""

import json
import logging
from pathlib import Path
from threading import Lock
from urllib.error import HTTPError, URLError
from uuid import uuid4

from chain import CHAIN_ID, CONTRACT_ADDRESS
from collection import fetch_collection, write_json_atomic
from cosmo import fetch_public_account


DEFAULT_DIRECTORY = Path(__file__).resolve().parent / "data" / "collections" / str(CHAIN_ID) / CONTRACT_ADDRESS
MAX_JOBS = 20
logger = logging.getLogger(__name__)


class CollectionBusyError(Exception):
    pass


class CollectionJobs:
    def __init__(self, directory: Path = DEFAULT_DIRECTORY):
        self.directory = directory
        self._jobs = {}
        self._active_id = None
        self._lock = Lock()

    def create(self, nickname: str) -> tuple[dict, bool]:
        with self._lock:
            if self._active_id:
                active = self._jobs[self._active_id]
                if active["status"] in ("queued", "running"):
                    if active["nickname"].casefold() == nickname.casefold():
                        return active.copy(), False
                    raise CollectionBusyError("另一個收藏查詢正在進行，請稍後重試。")
            while len(self._jobs) >= MAX_JOBS:
                oldest = next(key for key, job in self._jobs.items() if job["status"] in ("succeeded", "failed"))
                del self._jobs[oldest]
            job_id = uuid4().hex
            job = {
                "job_id": job_id, "nickname": nickname, "status": "queued",
                "progress": "準備查詢 COSMO 帳號…", "error": None, "snapshot": None,
            }
            self._jobs[job_id] = job
            self._active_id = job_id
            return job.copy(), True

    def get(self, job_id: str) -> dict:
        with self._lock:
            return self._jobs[job_id].copy()

    def _update(self, job_id: str, **changes) -> None:
        with self._lock:
            self._jobs[job_id].update(changes)

    def latest(self) -> dict:
        return json.loads((self.directory / "latest.json").read_text(encoding="utf-8"))

    def run(self, job_id: str) -> None:
        job = self.get(job_id)
        self._update(job_id, status="running", progress="正在查詢公開 COSMO 帳號…")
        try:
            try:
                account = fetch_public_account(job["nickname"])
            except HTTPError as error:
                if error.code == 404:
                    raise ValueError(f"找不到 COSMO 暱稱「{job['nickname']}」。") from error
                raise
            snapshot = fetch_collection(account, progress=lambda message: self._update(job_id, progress=message))
            cards = snapshot.get("objekts")
            if snapshot.get("complete") is not True or snapshot.get("account") != account or not isinstance(cards, list):
                raise ValueError("收藏資料不完整或帳號不符，已保留上次成功資料。")
            token_ids = [card.get("external_token_id") for card in cards if isinstance(card, dict)]
            if len(token_ids) != len(cards) or not all(isinstance(token, str) for token in token_ids) or len(set(token_ids)) != snapshot.get("total") or len(cards) != snapshot.get("total"):
                raise ValueError("收藏張數或個別 Token ID 不符，已保留上次成功資料。")
            # 先保留該錢包的成功資料，再更新最近一次查詢；不更動舊的教學 JSON。
            write_json_atomic(self.directory / f"{account['address'].lower()}.json", snapshot)
            write_json_atomic(self.directory / "latest.json", snapshot)
            self._update(job_id, status="succeeded", progress=f"讀取完成：{snapshot['total']} 張收藏。", snapshot=snapshot)
        except HTTPError as error:
            self._update(job_id, status="failed", error=f"來源服務回傳 HTTP {error.code}，請稍後重試。")
        except (URLError, OSError):
            self._update(job_id, status="failed", error="無法完成資料連線或儲存，請稍後重試。")
        except ValueError as error:
            self._update(job_id, status="failed", error=str(error))
        except Exception:
            logger.exception("Unexpected collection query failure")
            self._update(job_id, status="failed", error="收藏查詢發生錯誤，請稍後重試。")
        finally:
            with self._lock:
                if self._active_id == job_id:
                    self._active_id = None
