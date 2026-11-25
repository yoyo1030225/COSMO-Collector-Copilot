"""本機收藏查詢工作：回報進度、保留成功快照，同時只執行一個查詢。"""

import json
import logging
from pathlib import Path
from threading import Lock
from urllib.error import HTTPError, URLError
from uuid import uuid4

from chain import CHAIN_ID, CONTRACT_ADDRESS, SnapshotBlockChangedError
from collection import MissingMetadataError, fetch_collection, write_json_atomic
from cosmo import fetch_public_account


DEFAULT_DIRECTORY = Path(__file__).resolve().parent / "data" / "collections" / str(CHAIN_ID) / CONTRACT_ADDRESS
MAX_JOBS = 20
CARDS_PER_UPDATE = 300
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
                        return self._public_job(active), False
                    raise CollectionBusyError("另一個收藏查詢正在進行，請稍後重試。")
            while len(self._jobs) >= MAX_JOBS:
                oldest = next(key for key, job in self._jobs.items() if job["status"] in ("succeeded", "failed"))
                del self._jobs[oldest]
            job_id = uuid4().hex
            job = {
                "job_id": job_id, "nickname": nickname, "status": "queued",
                "progress": "準備查詢 COSMO 帳號…", "error": None, "snapshot": None, "account": None,
                "_token_ids": None, "_cards": [], "_owned_tokens": set(), "_priority_ids": (),
            }
            self._jobs[job_id] = job
            self._active_id = job_id
            return self._public_job(job), True

    @staticmethod
    def _public_job(job: dict) -> dict:
        return {key: value for key, value in job.items() if not key.startswith("_")}

    def get(self, job_id: str, *, cursor: int | None = None, include_tokens: bool = False) -> dict:
        with self._lock:
            job = self._jobs[job_id]
            response = self._public_job(job)
            if cursor is None:
                return response

            snapshot = response.pop("snapshot")
            tokens = job["_token_ids"]
            cards = job["_cards"][cursor:cursor + CARDS_PER_UPDATE]
            next_cursor = cursor + len(cards)
            response.update(
                total=len(tokens) if tokens is not None else None,
                token_ids=tokens if include_tokens else None,
                cards=cards,
                next_cursor=next_cursor,
                has_more=next_cursor < len(job["_cards"]),
                result={key: value for key, value in snapshot.items() if key != "objekts"} if snapshot else None,
            )
            return response

    def _update(self, job_id: str, **changes) -> None:
        with self._lock:
            self._jobs[job_id].update(changes)

    def _append_card(self, job_id: str, card: dict) -> None:
        with self._lock:
            self._jobs[job_id]["_cards"].append(card)

    def _publish_tokens(self, job_id: str, tokens: list[str]) -> None:
        self._update(
            job_id, _token_ids=tuple(tokens), _owned_tokens=set(tokens),
            progress="持有清單已核對，正在讀取卡片資料…",
        )

    def prioritize(self, job_id: str, token_ids: list[str]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if job["status"] == "running":
                job["_priority_ids"] = tuple(token for token in token_ids if token in job["_owned_tokens"])

    def _priority(self, job_id: str) -> tuple[str, ...]:
        with self._lock:
            return self._jobs[job_id]["_priority_ids"]

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
            self._update(job_id, account=account, progress="已找到帳號，正在查詢鏈上持有清單…")
            snapshot = fetch_collection(
                account,
                progress=lambda message: self._update(job_id, progress=message),
                on_tokens=lambda tokens: self._publish_tokens(job_id, tokens),
                on_card=lambda card: self._append_card(job_id, card),
                get_priority=lambda: self._priority(job_id),
            )
            cards = snapshot.get("objekts")
            if snapshot.get("complete") is not True or snapshot.get("account") != account or not isinstance(cards, list):
                raise ValueError("收藏資料不完整或帳號不符，已保留上次成功資料。")
            token_ids = [card.get("external_token_id") for card in cards if isinstance(card, dict)]
            if len(token_ids) != len(cards) or not all(isinstance(token, str) for token in token_ids) or len(set(token_ids)) != snapshot.get("total") or len(cards) != snapshot.get("total"):
                raise ValueError("收藏張數或個別 Token ID 不符，已保留上次成功資料。")
            # 先保留該錢包的成功資料，再更新最近一次查詢；不更動 CLI 匯出檔。
            write_json_atomic(self.directory / f"{account['address'].lower()}.json", snapshot)
            write_json_atomic(self.directory / "latest.json", snapshot)
            self._update(job_id, status="succeeded", progress=f"讀取完成：{snapshot['total']} 張收藏。", snapshot=snapshot)
        except HTTPError as error:
            self._update(job_id, status="failed", error=f"來源服務回傳 HTTP {error.code}，請稍後重試。")
        except (URLError, OSError):
            self._update(job_id, status="failed", error="資料來源暫時無法連線或快照無法儲存，請重新讀取收藏。")
        except MissingMetadataError as error:
            self._update(job_id, status="failed", error=f"鏈上持有清單已核對。{error.count:,} 張的卡片資料暫時無法取得，可重新讀取補齊。")
        except SnapshotBlockChangedError as error:
            self._update(job_id, status="failed", error=str(error), _token_ids=None, _cards=[])
        except ValueError as error:
            self._update(job_id, status="failed", error=str(error))
        except Exception:
            logger.exception("Unexpected collection query failure")
            self._update(job_id, status="failed", error="收藏查詢發生錯誤，請稍後重試。")
        finally:
            with self._lock:
                job = self._jobs.get(job_id)
                if job is not None:
                    job["_owned_tokens"].clear()
                    job["_priority_ids"] = ()
                if self._active_id == job_id:
                    self._active_id = None
