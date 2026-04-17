import os

from backend.app import app
from backend.config import PROJECT_ROOT, load_config, startup_diagnostics, validate_config
from backend.logging_utils import log_event
from backend.startup_guard import ensure_single_instance


if __name__ == '__main__':
    cfg = load_config()
    startup_diagnostics(cfg)
    cfg_ok, cfg_errors = validate_config(cfg)
    if not cfg_ok:
        log_event('startup_config_invalid', level='ERROR', errors=cfg_errors)
        raise SystemExit('設定檢查失敗，請修正後再啟動。')

    lock_error = ensure_single_instance(PROJECT_ROOT)
    if lock_error:
        log_event('startup_single_instance_failed', level='ERROR', detail=lock_error)
        raise SystemExit(lock_error)

    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
