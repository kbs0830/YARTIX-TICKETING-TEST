import os
import secrets
import uuid

from flask import Flask, g, jsonify, render_template, request, send_from_directory

from .config import FRONTEND_DIR, PROJECT_ROOT, load_config, startup_diagnostics, validate_config
from .email_service import EmailService, build_push_message
from .errors import E_INVALID_PAYLOAD, E_SHEET_SCHEMA, E_SHEET_UNAVAILABLE, E_SHEET_WRITE, E_VALIDATION
from .logging_utils import log_event
from .models import Participant
from .registration_service import RegistrationService
from .sheet_service import SheetService
from .startup_guard import ensure_single_instance

app = Flask(
    __name__,
    template_folder=os.path.join(FRONTEND_DIR, 'templates'),
    static_folder=os.path.join(FRONTEND_DIR, 'static'),
)
app.secret_key = secrets.token_hex(16)

cfg = load_config()
sheet_service = SheetService(cfg)
email_service = EmailService(cfg)
registration_service = RegistrationService(cfg, sheet_service)


def _build_bootstrap_payload(request_id: str):
    warning_message = ''
    error_code = ''
    schema_version = ''

    try:
        rem = sheet_service.remaining_seats()
        schema_version = sheet_service.get_schema_version()
        if schema_version != cfg.sheet_schema_version:
            warning_message = 'Google Sheet 欄位版本與系統設定不一致，已嘗試自動修正。'
            error_code = E_SHEET_SCHEMA
    except Exception as e:
        rem = sum(cfg.initial_seats_per_car)
        warning_message = '目前無法同步剩餘座位，系統已切換為暫時模式，仍可先填寫報名資料。'
        error_code = E_SHEET_UNAVAILABLE
        log_event(
            'bootstrap_fallback',
            level='ERROR',
            error_code=error_code,
            request_id=request_id,
            detail=str(e),
        )

    return {
        'ok': True,
        'remaining': rem,
        'sold_out': rem <= 0,
        'notice': cfg.real_name_notice,
        'warning': warning_message,
        'error_code': error_code,
        'open_hour': cfg.open_hour,
        'registration_end_date': cfg.registration_end_date,
        'ticket_types': cfg.ticket_types,
        'food_types': cfg.food_types,
        'addons': cfg.addons,
        'bank_info': cfg.bank_info,
        'line_link': cfg.line_group_link,
    }


def validate_participant(person):
    return registration_service.validate_participant(Participant.from_dict(person))


def build_registration_rows(participants):
    typed = [Participant.from_dict(p) for p in participants]
    return registration_service.build_registration_rows(typed)


def build_payment_email_body(rows, total_amount):
    return email_service.build_payment_email_body(rows, total_amount, cfg.bank_info, cfg.line_group_link)


@app.before_request
def bind_request_id():
    g.request_id = request.headers.get('X-Request-ID', '') or str(uuid.uuid4())


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        app.static_folder,
        'www.png',
        mimetype='image/png'
    )


@app.route('/.well-known/appspecific/com.chrome.devtools.json')
def chrome_devtools_probe():
    return ('', 204)


@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-Request-ID'] = getattr(g, 'request_id', '')
    return response


@app.route('/api/bootstrap', methods=['GET'])
def api_bootstrap():
    payload = _build_bootstrap_payload(g.request_id)
    return jsonify(payload)


@app.route('/api/register', methods=['POST'])
def api_register():
    payload = request.get_json(silent=True) or {}
    participants = payload.get('participants', [])
    if not isinstance(participants, list):
        return jsonify({
            'ok': False,
            'error_code': E_INVALID_PAYLOAD,
            'message': 'participants 欄位格式錯誤',
        }), 400

    try:
        ok, message, new_data, total_amount = build_registration_rows(participants)
    except Exception as e:
        log_event(
            'registration_sheet_unavailable',
            level='ERROR',
            error_code=E_SHEET_UNAVAILABLE,
            request_id=g.request_id,
            detail=str(e),
        )
        return jsonify({
            'ok': False,
            'error_code': E_SHEET_UNAVAILABLE,
            'message': f'報名系統暫時無法連線資料庫：{str(e)}',
        }), 503

    if not ok:
        return jsonify({
            'ok': False,
            'error_code': E_VALIDATION,
            'message': message,
        }), 400

    write_ok, write_error = sheet_service.append_rows_with_dedup(new_data)
    if not write_ok:
        log_event(
            'sheet_write_failed',
            level='ERROR',
            error_code=E_SHEET_WRITE,
            request_id=g.request_id,
            detail=write_error,
        )
        return jsonify({
            'ok': False,
            'error_code': E_SHEET_WRITE,
            'message': '資料寫入失敗，請稍後再試',
        }), 500

    email_ok, email_error_code, email_error = email_service.send_payment_email(new_data, total_amount, cfg.bank_info, cfg.line_group_link)
    if not email_ok:
        log_event(
            'payment_email_failed',
            level='ERROR',
            error_code=email_error_code,
            request_id=g.request_id,
            detail=email_error,
        )

    push_ok, push_error_code, push_error = email_service.send_push_notification(build_push_message(new_data))
    if not push_ok:
        log_event(
            'push_notification_failed',
            level='ERROR',
            error_code=push_error_code,
            request_id=g.request_id,
            detail=push_error,
        )

    return jsonify({
        'ok': True,
        'data': new_data,
        'bank_info': cfg.bank_info,
        'total_amount': total_amount,
        'line_link': cfg.line_group_link,
        'email_sent': email_ok,
        'email_error_code': email_error_code,
        'request_id': g.request_id,
    })


@app.route('/api/retry-email-queue', methods=['POST'])
def api_retry_email_queue():
    resent, remain = email_service.retry_email_queue()
    if resent == 0 and remain == 0:
        return jsonify({'ok': True, 'message': '目前沒有待重送 email', 'resent': 0, 'remain': 0})
    return jsonify({'ok': True, 'resent': resent, 'remain': remain})


if __name__ == '__main__':
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
