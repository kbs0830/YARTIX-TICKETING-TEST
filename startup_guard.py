import os
from typing import Optional

from logging_utils import log_event

_LOCK_FILE = '.app.pid'


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def ensure_single_instance(base_dir: str) -> Optional[str]:
    lock_path = os.path.join(base_dir, _LOCK_FILE)
    pid = os.getpid()

    if os.path.exists(lock_path):
        try:
            with open(lock_path, 'r', encoding='utf-8') as f:
                old_pid = int((f.read() or '0').strip())
            if old_pid > 0 and old_pid != pid and _pid_exists(old_pid):
                return f'偵測到另一個 app.py 已在執行（PID: {old_pid}），請先停止舊進程。'
        except Exception:
            pass

    with open(lock_path, 'w', encoding='utf-8') as f:
        f.write(str(pid))

    log_event('single_instance_lock_acquired', pid=pid, lock_file=lock_path)
    return None
