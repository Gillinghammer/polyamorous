from __future__ import annotations

import time
from typing import Tuple


def format_time_until(epoch_seconds: int) -> Tuple[str, str]:
    """Return (label, severity) where label like '3d', '5h', '45m' and severity in {'urgent','soon','normal'}.

    - urgent: < 24h
    - soon: < 72h
    - normal: otherwise
    """
    now = int(time.time())
    remaining = max(0, int(epoch_seconds or 0) - now)
    days = remaining // 86400
    hours = (remaining % 86400) // 3600
    minutes = (remaining % 3600) // 60

    if days > 0:
        label = f"{days}d"
    elif hours > 0:
        label = f"{hours}h"
    else:
        label = f"{minutes}m"

    if remaining < 24 * 3600:
        sev = "urgent"
    elif remaining < 72 * 3600:
        sev = "soon"
    else:
        sev = "normal"
    return label, sev


