import json
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

from logging_utils import log_event

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_env_file(env_path: str) -> None:
    if not os.path.exists(env_path):
        return

    with open(env_path, 'r', encoding='utf-8') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_env_file(os.path.join(BASE_DIR, '.env'))


@dataclass(frozen=True)
class AppConfig:
    google_credentials_path: str
    google_sheet_name: str
    num_cars: int
    initial_seats_per_car: List[int]
    line_group_link: str
    ticket_types: Dict[str, int]
    food_types: List[str]
    addons: Dict[str, Dict[str, int | str]]
    dinner_price: int
    real_name_notice: str
    open_hour: int
    registration_end_date: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_app_password: str
    smtp_from: str
    payment_deadline_text: str
    push_enabled: bool
    push_provider: str
    push_target_email: str
    push_telegram_bot_token: str
    push_telegram_chat_id: str
    push_line_notify_token: str
    email_retry_queue_file: str
    bank_info: Dict[str, str]
    sheet_schema_version: str


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _to_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_config() -> AppConfig:
    smtp_username = os.environ.get('SMTP_USERNAME', '').strip()

    return AppConfig(
        google_credentials_path=os.environ.get('GOOGLE_CREDENTIALS_PATH', os.path.join(BASE_DIR, 'credentials.json')),
        google_sheet_name=os.environ.get('GOOGLE_SHEET_NAME', '主售票系統  2026 春映洄瀾，拾光'),
        num_cars=10,
        initial_seats_per_car=[100, 1000, 102, 100, 100, 0, 26, 50, 50, 50],
        line_group_link='https://line.me/R/ti/g/F_CbUHyWFy',
        ticket_types={
            '一般套票': 2600,
            '優待套票(12歲以下/65歲以上)': 2500,
        },
        food_types=['葷', '素'],
        addons={
            'easycard': {'label': '悠遊卡', 'price': 300},
        },
        dinner_price=80,
        real_name_notice='本次活動採實名制，活動當日請攜帶身份證明（身份證或健保卡電子證明）',
        open_hour=12,
        registration_end_date=os.environ.get('REGISTRATION_END_DATE', '2026-06-06'),
        smtp_host=os.environ.get('SMTP_HOST', 'smtp.gmail.com'),
        smtp_port=_to_int(os.environ.get('SMTP_PORT', '587'), 587),
        smtp_username=smtp_username,
        smtp_app_password=os.environ.get('SMTP_APP_PASSWORD', '').strip(),
        smtp_from=os.environ.get('SMTP_FROM', smtp_username).strip(),
        payment_deadline_text=os.environ.get('PAYMENT_DEADLINE_TEXT', '請於 3 日內完成匯款'),
        push_enabled=_to_bool(os.environ.get('PUSH_ENABLED', 'false'), default=False),
        push_provider=os.environ.get('PUSH_PROVIDER', '').strip().lower(),
        push_target_email=os.environ.get('PUSH_TARGET_EMAIL', '').strip(),
        push_telegram_bot_token=os.environ.get('PUSH_TELEGRAM_BOT_TOKEN', '').strip(),
        push_telegram_chat_id=os.environ.get('PUSH_TELEGRAM_CHAT_ID', '').strip(),
        push_line_notify_token=os.environ.get('PUSH_LINE_NOTIFY_TOKEN', '').strip(),
        email_retry_queue_file=os.path.join(BASE_DIR, 'email_retry_queue.jsonl'),
        bank_info={
            '銀行': os.environ.get('BANK_NAME', '中國信託銀行822'),
            '帳號': os.environ.get('BANK_ACCOUNT', '7835-4029-2705'),
            '戶名': os.environ.get('BANK_HOLDER', '雲觀藝術工作室'),
        },
        sheet_schema_version=os.environ.get('SHEET_SCHEMA_VERSION', '2026.04.17.v1'),
    )


def startup_diagnostics(cfg: AppConfig) -> None:
    try:
        has_inline_google_json = bool(os.environ.get('GOOGLE_CREDENTIALS_JSON', '').strip())
    except json.JSONDecodeError:
        has_inline_google_json = True

    checks = {
        'smtp_host': cfg.smtp_host,
        'smtp_port': cfg.smtp_port,
        'smtp_username_configured': bool(cfg.smtp_username),
        'smtp_password_configured': bool(cfg.smtp_app_password),
        'smtp_from_configured': bool(cfg.smtp_from),
        'google_sheet_name': cfg.google_sheet_name,
        'google_creds_json_configured': has_inline_google_json,
        'google_creds_file_exists': os.path.exists(cfg.google_credentials_path),
        'push_enabled': cfg.push_enabled,
        'push_provider': cfg.push_provider or '(disabled)',
        'sheet_schema_version': cfg.sheet_schema_version,
    }
    log_event('startup_config_check', **checks)


def validate_config(cfg: AppConfig) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if cfg.smtp_port <= 0:
        errors.append('SMTP_PORT 必須是正整數')
    if len(cfg.initial_seats_per_car) != cfg.num_cars:
        errors.append('INITIAL_SEATS_PER_CAR 長度需與 NUM_CARS 一致')
    if sum(cfg.initial_seats_per_car) <= 0:
        errors.append('總座位需大於 0')
    return len(errors) == 0, errors
