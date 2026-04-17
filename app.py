from flask import Flask, render_template, request, jsonify, send_from_directory
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import secrets
import re
import smtplib
from email.message import EmailMessage
from urllib import request as urlrequest
from urllib import parse as urlparse

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_env_file(env_path):
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
            if key:
                os.environ[key] = value


load_env_file(os.path.join(BASE_DIR, '.env'))

# ---------------- 配置 ----------------
GOOGLE_CREDENTIALS = os.environ.get(
    'GOOGLE_CREDENTIALS_PATH',
    os.path.join(BASE_DIR, 'credentials.json')
)
GOOGLE_SHEET_NAME = os.environ.get('GOOGLE_SHEET_NAME', '主售票系統  2026 春映洄瀾，拾光')
NUM_CARS = 10
INITIAL_SEATS_PER_CAR = [100,1000,102,100,100,0,26,50,50,50]
LINE_GROUP_LINK = "https://line.me/R/ti/g/F_CbUHyWFy"
TICKET_TYPES = {
    '一般套票': 2600,
    '優待套票(12歲以下/65歲以上)': 2500,
}
FOOD_TYPES = ['葷','素']
ADDONS = {
    'easycard': {'label': '悠遊卡', 'price': 300},
}

DINNER_PRICE = 80
REAL_NAME_NOTICE = '本次活動採實名制，活動當日請攜帶身份證明（身份證或健保卡電子證明）'
OPEN_HOUR = 12
REGISTRATION_END_DATE = os.environ.get('REGISTRATION_END_DATE', '2026-06-06')

SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '').strip()
SMTP_APP_PASSWORD = os.environ.get('SMTP_APP_PASSWORD', '').strip()
SMTP_FROM = os.environ.get('SMTP_FROM', SMTP_USERNAME).strip()
PAYMENT_DEADLINE_TEXT = os.environ.get('PAYMENT_DEADLINE_TEXT', '請於 3 日內完成匯款')

PUSH_ENABLED = os.environ.get('PUSH_ENABLED', 'false').strip().lower() in ('1', 'true', 'yes', 'on')
PUSH_PROVIDER = os.environ.get('PUSH_PROVIDER', '').strip().lower()
PUSH_TARGET_EMAIL = os.environ.get('PUSH_TARGET_EMAIL', '').strip()
PUSH_TELEGRAM_BOT_TOKEN = os.environ.get('PUSH_TELEGRAM_BOT_TOKEN', '').strip()
PUSH_TELEGRAM_CHAT_ID = os.environ.get('PUSH_TELEGRAM_CHAT_ID', '').strip()
PUSH_LINE_NOTIFY_TOKEN = os.environ.get('PUSH_LINE_NOTIFY_TOKEN', '').strip()

EMAIL_RETRY_QUEUE_FILE = os.path.join(BASE_DIR, 'email_retry_queue.jsonl')

BANK_INFO = {
    '銀行': '中國信託銀行822',
    '帳號': '7835-4029-2705',
    '戶名': '雲觀藝術工作室',
}

# ---------------- Google Sheets ----------------

def get_google_sheet():
    scope = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
    ]
    credentials_json = os.environ.get('GOOGLE_CREDENTIALS_JSON', '').strip()
    if credentials_json:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            json.loads(credentials_json),
            scope
        )
    else:
        if not os.path.exists(GOOGLE_CREDENTIALS):
            raise RuntimeError(
                '找不到 Google 憑證。請在 Render 設定 GOOGLE_CREDENTIALS_JSON，'
                '或提供有效的 GOOGLE_CREDENTIALS_PATH。'
            )
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            GOOGLE_CREDENTIALS,
            scope
        )
    client = gspread.authorize(creds)
    sheet = client.open(GOOGLE_SHEET_NAME).sheet1

    header_row = [
    '姓名','性別','出生年月日','身分證字號','電話號碼','電子郵件',
    '票種','飲食選擇',
    '匯款銀行','匯款末四碼','備註',
    '報名時間',
    '加購_easycard',
    '金額',
    '報名序號'
    ]

    existing_headers = sheet.row_values(1)
    if existing_headers == []:
        sheet.append_row(header_row)
    else:
        sheet.update(range_name='A1:O1', values=[header_row])

    return sheet

# ---------------- 剩餘座位 ----------------

def remaining_seats():

    sheet = get_google_sheet()
    records = sheet.get_all_records()

    booked = len(records)

    total_seats = sum(INITIAL_SEATS_PER_CAR)

    return max(0, total_seats - booked)

# ---------------- 序號處理 ----------------

def build_serial_code(timestamp_text, sequence_number):
    date_text = timestamp_text[:10].replace('-', '')
    return f'{date_text}{sequence_number:03d}'


def is_valid_date_text(date_text):
    try:
        datetime.strptime(date_text, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def validate_participant(person):
    name = str(person.get('name', '')).strip()
    gender = str(person.get('gender', '')).strip()
    dob = str(person.get('dob', '')).strip()
    id_number = str(person.get('id_number', '')).strip().upper()
    phone = str(person.get('phone', '')).strip()
    email = str(person.get('email', '')).strip()
    ticket_type = str(person.get('ticket_type', '')).strip()
    food_types = str(person.get('food_types', '')).strip()

    if not (2 <= len(name) <= 20):
        return False, '姓名長度需為 2 到 20 字'
    if gender not in ('男', '女'):
        return False, '性別格式不正確'
    if not is_valid_date_text(dob):
        return False, '出生年月日格式不正確'
    if not re.fullmatch(r'[A-Z][12]\d{8}', id_number):
        return False, '身分證字號格式不正確'
    if not re.fullmatch(r'09\d{8}', phone):
        return False, '電話號碼格式不正確'
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        return False, '電子郵件格式不正確'
    if ticket_type not in TICKET_TYPES:
        return False, '票種格式不正確'
    if food_types not in FOOD_TYPES:
        return False, '飲食選擇格式不正確'

    addons = person.get('addons', {})
    for key in addons:
        if key not in ADDONS:
            return False, '加購項目格式不正確'
        qty = addons.get(key, 0)
        if not isinstance(qty, int) or qty < 0 or qty > 20:
            return False, '加購數量格式不正確'

    return True, ''


def assign_serial(index, timestamp_text):
    return build_serial_code(timestamp_text, index + 1)


def is_valid_email_address(email):
    return bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', str(email).strip()))


def append_failed_email_task(task):
    try:
        with open(EMAIL_RETRY_QUEUE_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(task, ensure_ascii=False) + '\n')
    except Exception as e:
        print('寫入 email 重送佇列失敗:', e)


def send_email_smtp(to_emails, subject, body):
    recipients = [email for email in to_emails if is_valid_email_address(email)]
    if not recipients:
        return False, '缺少有效收件者 email'
    if not (SMTP_USERNAME and SMTP_APP_PASSWORD and SMTP_FROM):
        return False, 'SMTP 環境變數未完整設定'
    if SMTP_APP_PASSWORD in ('你的16碼AppPassword', 'YOUR_16_CHAR_APP_PASSWORD'):
        return False, 'SMTP_APP_PASSWORD 仍是範例文字，請改成 Gmail App Password（16 碼）'

    try:
        SMTP_APP_PASSWORD.encode('ascii')
    except UnicodeEncodeError:
        return False, 'SMTP_APP_PASSWORD 含非 ASCII 字元，請使用 Gmail App Password（16 碼英數）'

    message = EmailMessage()
    message['From'] = SMTP_FROM
    message['To'] = ', '.join(recipients)
    message['Subject'] = subject
    message.set_content(body, charset='utf-8')

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_APP_PASSWORD)
            server.send_message(message)
        return True, ''
    except Exception as e:
        return False, str(e)


def build_payment_email_body(rows, total_amount):
    def to_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def mask_id_number(id_number):
        text = str(id_number or '').strip().upper()
        if len(text) != 10:
            return text
        return f"{text[:3]}****{text[-3:]}"

    serials = [str(row.get('報名序號', '')).strip() for row in rows]
    serials = [s for s in serials if s]

    easycard_cfg = ADDONS.get('easycard', {'label': '悠遊卡', 'price': 0})
    easycard_label = easycard_cfg.get('label', '悠遊卡')
    easycard_price = to_int(easycard_cfg.get('price', 0))

    total_easycard_qty = 0
    addon_summary_map = {key: 0 for key in ADDONS}
    participant_lines = []
    for row in rows:
        addon_parts = []
        for key, addon_cfg in ADDONS.items():
            qty = max(0, to_int(row.get(f'加購_{key}', 0)))
            addon_summary_map[key] += qty
            if key == 'easycard':
                total_easycard_qty += qty
            if qty > 0:
                addon_price = to_int(addon_cfg.get('price', 0))
                addon_parts.append(f"{addon_cfg.get('label', key)} {qty} 份（NT$ {qty * addon_price}）")

        addon_text = '、'.join(addon_parts) if addon_parts else '無'
        serial_text = str(row.get('報名序號', '')).strip() or '無'
        participant_lines.append(
            f"- 姓名：{row.get('姓名', '')}\n"
            f"  報名序號：{serial_text}\n"
            f"  身分證：{mask_id_number(row.get('身分證字號', ''))}\n"
            f"  出生日期：{row.get('出生年月日', '')}\n"
            f"  聯絡電話：{row.get('電話號碼', '')}\n"
            f"  Email：{row.get('電子郵件', '')}\n"
            f"  票種：{row.get('票種', '')}\n"
            f"  飲食：{row.get('飲食選擇', '')}\n"
            f"  加購：{addon_text}\n"
            f"  小計：NT$ {row.get('金額', 0)}"
        )

    participants_text = '\n'.join(participant_lines)
    easycard_summary = (
        f"{easycard_label}：有（共 {total_easycard_qty} 張，NT$ {total_easycard_qty * easycard_price}）"
        if total_easycard_qty > 0
        else f"{easycard_label}：無"
    )
    addon_summary_text = ', '.join(
        f"{cfg.get('label', key)} {addon_summary_map[key]} 份"
        for key, cfg in ADDONS.items()
    )

    return (
        '您好，您的報名已完成，以下為付款資訊：\n\n'
        f"報名人數：{len(rows)}\n"
        f"銀行：{BANK_INFO['銀行']}\n"
        f"帳號：{BANK_INFO['帳號']}\n"
        f"戶名：{BANK_INFO['戶名']}\n"
        f"總金額：NT$ {total_amount}\n"
        f"{easycard_summary}\n"
        f"其他加購統計：{addon_summary_text}\n"
        f"報名序號：{', '.join(serials) if serials else '無'}\n"
        f"付款期限：{PAYMENT_DEADLINE_TEXT}\n\n"
        f'參加者完整明細：\n{participants_text}\n\n'
        f'LINE 群組連結：{LINE_GROUP_LINK}\n\n'
        '提醒：若匯款後需回報，請於信件主旨附上報名序號。\n'
        '若有疑問請回覆本信，謝謝。'
    )


def send_payment_email(rows, total_amount):
    recipients = []
    for row in rows:
        email = str(row.get('電子郵件', '')).strip()
        if email and email not in recipients:
            recipients.append(email)

    subject = '【春映洄瀾，拾光】付款資訊通知'
    body = build_payment_email_body(rows, total_amount)
    ok, message = send_email_smtp(recipients, subject, body)
    if ok:
        return True, ''

    append_failed_email_task({
        'type': 'payment_info',
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'to_emails': recipients,
        'subject': subject,
        'body': body,
        'error': message,
        'serial_numbers': [row.get('報名序號', '') for row in rows],
    })
    return False, message


def send_push_notification(message):
    if not PUSH_ENABLED:
        return True, ''

    provider = PUSH_PROVIDER
    if provider == 'gmail':
        if not PUSH_TARGET_EMAIL:
            return False, 'PUSH_TARGET_EMAIL 未設定'
        return send_email_smtp([PUSH_TARGET_EMAIL], '報名成功通知', message)

    if provider == 'telegram':
        if not PUSH_TELEGRAM_BOT_TOKEN or not PUSH_TELEGRAM_CHAT_ID:
            return False, 'Telegram 推送參數未設定'
        api_url = f'https://api.telegram.org/bot{PUSH_TELEGRAM_BOT_TOKEN}/sendMessage'
        payload = urlparse.urlencode({
            'chat_id': PUSH_TELEGRAM_CHAT_ID,
            'text': message,
        }).encode('utf-8')
        req = urlrequest.Request(api_url, data=payload)
        try:
            with urlrequest.urlopen(req, timeout=15) as resp:
                if resp.status >= 400:
                    return False, f'Telegram HTTP {resp.status}'
            return True, ''
        except Exception as e:
            return False, str(e)

    if provider == 'line':
        if not PUSH_LINE_NOTIFY_TOKEN:
            return False, 'PUSH_LINE_NOTIFY_TOKEN 未設定'
        payload = urlparse.urlencode({'message': message}).encode('utf-8')
        req = urlrequest.Request(
            'https://notify-api.line.me/api/notify',
            data=payload,
            headers={'Authorization': f'Bearer {PUSH_LINE_NOTIFY_TOKEN}'},
        )
        try:
            with urlrequest.urlopen(req, timeout=15) as resp:
                if resp.status >= 400:
                    return False, f'LINE HTTP {resp.status}'
            return True, ''
        except Exception as e:
            return False, str(e)

    return False, 'PUSH_PROVIDER 未設定或不支援'


def build_push_message(rows):
    lines = ['報名成功通知']
    for row in rows:
        lines.append(
            f"姓名:{row.get('姓名', '')} 票種:{row.get('票種', '')} 金額:{row.get('金額', 0)} 序號:{row.get('報名序號', '')} 匯款末四碼:{row.get('匯款末四碼', '')}"
        )
    return '\n'.join(lines)

# ---------------- Google Sheet 寫入 ----------------

def google_sheets_append_safe(data_list):
    try:
        sheet = get_google_sheet()
        cols_order = [
        '姓名','性別','出生年月日','身分證字號','電話號碼','電子郵件',
        '票種','飲食選擇',
        '匯款銀行','匯款末四碼','備註',
        '報名時間',
        '加購_easycard',
        '金額',
        '報名序號'
        ]

        existing_records = sheet.get_all_records()
        existing_keys = set(
        (rec['身分證字號'], rec['報名時間'])
        for rec in existing_records
        )

        for row in data_list:
            key = (row['身分證字號'], row['報名時間'])
            if key not in existing_keys:
                values = [row.get(col,'') for col in cols_order]
                sheet.append_row(values)
        return True
    except Exception as e:
        print("Google Sheet同步錯誤:", e)
        return False


def build_registration_rows(participants):
    remaining = remaining_seats()
    if len(participants) == 0:
        return False, '至少要有 1 位參加者', None, None
    if len(participants) > remaining:
        return False, f'剩餘座位不足，目前僅剩 {remaining} 席', None, None

    sheet = get_google_sheet()
    existing_records = sheet.get_all_records()
    current_count = len(existing_records)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_data = []
    total_amount = 0

    for i, person in enumerate(participants):
        ok, message = validate_participant(person)
        if not ok:
            return False, message, None, None

        ticket_name = person.get('ticket_type', '')
        ticket_price = TICKET_TYPES.get(ticket_name, 0)

        addon_total = 0
        addon_quantities = {}
        incoming_addons = person.get('addons', {})
        for key, addon in ADDONS.items():
            qty = max(0, int(incoming_addons.get(key, 0)))
            addon_quantities[f'加購_{key}'] = qty
            addon_total += qty * addon['price']

        person_total = ticket_price + addon_total
        total_amount += person_total
        serial_number = assign_serial(current_count + i, timestamp)

        row = {
            '姓名': person.get('name', ''),
            '性別': person.get('gender', ''),
            '出生年月日': person.get('dob', ''),
            '身分證字號': person.get('id_number', ''),
            '電話號碼': person.get('phone', ''),
            '電子郵件': person.get('email', ''),
            '票種': ticket_name,
            '飲食選擇': person.get('food_types', ''),
            '匯款銀行': '',
            '匯款末四碼': '',
            '備註': '',
            '報名時間': timestamp,
            '金額': person_total,
            '報名序號': serial_number,
        }
        row.update(addon_quantities)
        new_data.append(row)

    return True, '', new_data, total_amount

# ---------------- 路由 ----------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/favicon.ico')
def favicon():
    # Serve a stable icon from static assets to avoid favicon 404 noise.
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'www.png',
        mimetype='image/png'
    )


@app.route('/.well-known/appspecific/com.chrome.devtools.json')
def chrome_devtools_probe():
    # Chrome may probe this endpoint locally; returning 204 avoids noisy logs.
    return ('', 204)


@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/api/bootstrap', methods=['GET'])
def api_bootstrap():
    warning_message = ''
    try:
        rem = remaining_seats()
    except Exception as e:
        # 即使 Sheet 暫時不可用，也先讓前端能載入並顯示表單。
        rem = sum(INITIAL_SEATS_PER_CAR)
        warning_message = '目前無法同步剩餘座位，系統已切換為暫時模式，仍可先填寫報名資料。'
        print('Bootstrap fallback:', e)

    return jsonify({
        'ok': True,
        'remaining': rem,
        'sold_out': rem <= 0,
        'notice': REAL_NAME_NOTICE,
        'warning': warning_message,
        'open_hour': OPEN_HOUR,
        'registration_end_date': REGISTRATION_END_DATE,
        'ticket_types': TICKET_TYPES,
        'food_types': FOOD_TYPES,
        'addons': ADDONS,
        'bank_info': BANK_INFO,
        'line_link': LINE_GROUP_LINK,
    })


@app.route('/api/register', methods=['POST'])
def api_register():
    payload = request.get_json(silent=True) or {}
    participants = payload.get('participants', [])

    try:
        ok, message, new_data, total_amount = build_registration_rows(participants)
    except Exception as e:
        return jsonify({
            'ok': False,
            'message': f'報名系統暫時無法連線資料庫：{str(e)}'
        }), 503

    if not ok:
        return jsonify({'ok': False, 'message': message}), 400

    if not google_sheets_append_safe(new_data):
        return jsonify({'ok': False, 'message': '資料寫入失敗，請稍後再試'}), 500

    email_ok, email_error = send_payment_email(new_data, total_amount)
    if not email_ok:
        print('付款資訊 Email 寄送失敗:', email_error)

    push_ok, push_error = send_push_notification(build_push_message(new_data))
    if not push_ok:
        print('報名推送失敗:', push_error)

    return jsonify({
        'ok': True,
        'data': new_data,
        'bank_info': BANK_INFO,
        'total_amount': total_amount,
        'line_link': LINE_GROUP_LINK,
        'email_sent': email_ok,
    })


@app.route('/api/retry-email-queue', methods=['POST'])
def api_retry_email_queue():
    if not os.path.exists(EMAIL_RETRY_QUEUE_FILE):
        return jsonify({'ok': True, 'message': '目前沒有待重送 email', 'resent': 0})

    resent = 0
    remain_tasks = []
    with open(EMAIL_RETRY_QUEUE_FILE, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]

    for line in lines:
        try:
            task = json.loads(line)
            ok, err = send_email_smtp(
                task.get('to_emails', []),
                task.get('subject', ''),
                task.get('body', ''),
            )
            if ok:
                resent += 1
            else:
                task['error'] = err
                remain_tasks.append(task)
        except Exception as e:
            remain_tasks.append({
                'type': 'unknown',
                'error': str(e),
                'raw': line,
            })

    with open(EMAIL_RETRY_QUEUE_FILE, 'w', encoding='utf-8') as f:
        for task in remain_tasks:
            f.write(json.dumps(task, ensure_ascii=False) + '\n')

    return jsonify({
        'ok': True,
        'resent': resent,
        'remain': len(remain_tasks),
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT",8080))
    app.run(host="0.0.0.0", port=port)
