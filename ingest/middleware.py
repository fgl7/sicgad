from __future__ import annotations

import logging
import threading
import time

from django.conf import settings
from django.core.cache import cache

from ingest.file_cleanup import cleanup_ingest_files, format_bytes

logger = logging.getLogger(__name__)

LAST_RUN_KEY = "ingest:auto_cleanup:last_run_ts"
LOCK_KEY = "ingest:auto_cleanup:lock"


class AutoIngestCleanupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._maybe_schedule_cleanup(request)
        return response

    def _maybe_schedule_cleanup(self, request) -> None:
        if not getattr(settings, "AUTO_INGEST_CLEANUP_ENABLED", True):
            return

        if request.method not in {"GET", "HEAD"}:
            return

        interval = int(getattr(settings, "AUTO_INGEST_CLEANUP_INTERVAL_SECONDS", 21600))
        interval = max(60, interval)
        now_ts = int(time.time())

        last_run_ts = int(cache.get(LAST_RUN_KEY, 0) or 0)
        if now_ts - last_run_ts < interval:
            return

        lock_timeout = int(getattr(settings, "AUTO_INGEST_CLEANUP_LOCK_TIMEOUT_SECONDS", 600))
        lock_timeout = max(60, lock_timeout)
        if not cache.add(LOCK_KEY, "1", lock_timeout):
            return

        cache.set(LAST_RUN_KEY, now_ts, timeout=max(interval * 2, 3600))

        thread = threading.Thread(target=self._run_cleanup, daemon=True)
        thread.start()

    def _run_cleanup(self) -> None:
        try:
            result = cleanup_ingest_files(
                apply_changes=True,
                instance_retention_days=int(
                    getattr(settings, "AUTO_INGEST_INSTANCE_RETENTION_DAYS", 90)
                ),
                batch_retention_days=int(
                    getattr(settings, "AUTO_INGEST_BATCH_RETENTION_DAYS", 180)
                ),
                orphan_retention_days=int(
                    getattr(settings, "AUTO_INGEST_ORPHAN_RETENTION_DAYS", 7)
                ),
                skip_orphans=bool(
                    getattr(settings, "AUTO_INGEST_SKIP_ORPHANS", False)
                ),
            )
            logger.info(
                "Auto cleanup ingest completado: %s archivos (%s)",
                result.total_count,
                format_bytes(result.total_bytes),
            )
            cache.set(LAST_RUN_KEY, int(time.time()), timeout=None)
        except Exception:
            logger.exception("Error ejecutando auto cleanup de ingest")
        finally:
            cache.delete(LOCK_KEY)
