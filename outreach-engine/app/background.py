from __future__ import annotations

import threading
from typing import Callable


def run_in_thread(fn: Callable[[], None]) -> None:
    t = threading.Thread(target=fn, daemon=True)
    t.start()

