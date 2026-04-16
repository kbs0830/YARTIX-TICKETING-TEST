from flask import Flask, render_template, request, jsonify
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import secrets
import re

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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

BANK_INFO = {
'銀行': os.environ.get('BANK_NAME', '請設定 BANK_NAME'),
'帳號': os.environ.get('BANK_ACCOUNT', '請設定 BANK_ACCOUNT'),
'戶名': os.environ.get('BANK_HOLDER', '請設定 BANK_HOLDER')
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
    '序號'
    ]

    existing_headers = sheet.row_values(1)
    if existing_headers == []:
        sheet.append_row(header_row)
    else:
        sheet.update('A1:O1', [header_row])

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
    bank_name = str(person.get('bank_name', '')).strip()
    bank_last4 = str(person.get('bank_last4', '')).strip()
    note = str(person.get('note', '')).strip()

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
    if not (2 <= len(bank_name) <= 40):
        return False, '匯款銀行名稱格式不正確'
    if not re.fullmatch(r'\d{4}', bank_last4):
        return False, '匯款末四碼格式不正確'
    if len(note) > 100:
        return False, '備註長度不可超過 100 字'

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
        '序號'
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
            '匯款銀行': person.get('bank_name', ''),
            '匯款末四碼': person.get('bank_last4', ''),
            '備註': person.get('note', ''),
            '報名時間': timestamp,
            '金額': person_total,
            '序號': serial_number,
        }
        row.update(addon_quantities)
        new_data.append(row)

    return True, '', new_data, total_amount

# ---------------- 路由 ----------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/bootstrap', methods=['GET'])
def api_bootstrap():
    rem = remaining_seats()
    return jsonify({
        'remaining': rem,
        'sold_out': rem <= 0,
        'notice': REAL_NAME_NOTICE,
        'open_hour': OPEN_HOUR,
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

    ok, message, new_data, total_amount = build_registration_rows(participants)
    if not ok:
        return jsonify({'ok': False, 'message': message}), 400

    if not google_sheets_append_safe(new_data):
        return jsonify({'ok': False, 'message': '資料寫入失敗，請稍後再試'}), 500

    return jsonify({
        'ok': True,
        'data': new_data,
        'bank_info': BANK_INFO,
        'total_amount': total_amount,
        'line_link': LINE_GROUP_LINK,
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT",8080))
    app.run(host="0.0.0.0", port=port)
