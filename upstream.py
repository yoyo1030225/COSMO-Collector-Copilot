"""為唯讀的上游查詢處理短暫連線錯誤與限流。"""

import time
from threading import Lock
from urllib.error import HTTPError, URLError


class UpstreamBusyError(ConnectionError):
    """上游在 HTTP 200 內回報 JSON-RPC 限流。"""


class RateLimitCooldown:
    """讓同一批並行查詢共用 HTTP 429 的等待時間。"""

    def __init__(self):
        self._lock = Lock()
        self._resume_at = 0.0

    def extend(self, delay: float) -> None:
        with self._lock:
            self._resume_at = max(self._resume_at, time.monotonic() + delay)

    def wait(self) -> None:
        while True:
            with self._lock:
                delay = self._resume_at - time.monotonic()
            if delay <= 0:
                return
            time.sleep(delay)


def retry_read(read, *, retry_not_found: bool = False, cooldown: RateLimitCooldown | None = None):
    for attempt in range(3):
        delay = 2 ** attempt
        if cooldown:
            cooldown.wait()
        try:
            return read()
        except HTTPError as error:
            retryable = error.code in (408, 429, 500, 502, 503, 504) or (retry_not_found and error.code == 404)
            if not retryable:
                raise
            after = error.headers.get("Retry-After", "").strip() if error.headers else ""
            if after.isascii() and after.isdecimal() and len(after) <= 6:
                delay = max(delay, min(int(after), 30))
            if cooldown and error.code == 429:
                cooldown.extend(delay)
                delay = 0  # 下一輪會等待共用的期限。
            if attempt == 2:
                raise
        except (URLError, TimeoutError, ConnectionError):
            if attempt == 2:
                raise
        if delay:
            time.sleep(delay)
