"""时间工具。任何层都可依赖，本模块不依赖任何层。"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp_to_epoch(value: str) -> int:
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except (TypeError, ValueError):
        return 0
