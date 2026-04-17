import json
import os
import threading
from typing import Dict, List, Tuple

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from config import AppConfig

HEADER_ROW = [
    '姓名', '性別', '出生年月日', '身分證字號', '電話號碼', '電子郵件',
    '票種', '飲食選擇',
    '匯款銀行', '匯款末四碼', '備註',
    '報名時間',
    '加購_easycard',
    '金額',
    '報名序號',
    '__schema_version',
]

COLS_ORDER = HEADER_ROW[:-1]
_SCHEMA_CELL = 'P2'
_append_lock = threading.Lock()


class SheetService:
    def __init__(self, config: AppConfig):
        self.config = config

    def get_google_sheet(self):
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive',
        ]
        credentials_json = os.environ.get('GOOGLE_CREDENTIALS_JSON', '').strip()
        if credentials_json:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(credentials_json), scope)
        else:
            if not os.path.exists(self.config.google_credentials_path):
                raise RuntimeError(
                    '找不到 Google 憑證。請在 Render 設定 GOOGLE_CREDENTIALS_JSON，或提供有效的 GOOGLE_CREDENTIALS_PATH。'
                )
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.config.google_credentials_path, scope)

        client = gspread.authorize(creds)
        sheet = client.open(self.config.google_sheet_name).sheet1
        self.ensure_schema(sheet)
        return sheet

    def ensure_schema(self, sheet) -> None:
        existing_headers = sheet.row_values(1)
        if not existing_headers:
            sheet.append_row(HEADER_ROW)
        else:
            sheet.update(range_name='A1:P1', values=[HEADER_ROW])

        sheet.update_acell(_SCHEMA_CELL, self.config.sheet_schema_version)

    def get_schema_version(self) -> str:
        sheet = self.get_google_sheet()
        return str(sheet.acell(_SCHEMA_CELL).value or '').strip()

    def remaining_seats(self) -> int:
        sheet = self.get_google_sheet()
        serial_col = sheet.col_values(15)
        booked = max(0, len(serial_col) - 1)
        total_seats = sum(self.config.initial_seats_per_car)
        return max(0, total_seats - booked)

    def get_registration_count(self) -> int:
        sheet = self.get_google_sheet()
        serial_col = sheet.col_values(15)
        return max(0, len(serial_col) - 1)

    def append_rows_with_dedup(self, data_list: List[Dict]) -> Tuple[bool, str]:
        with _append_lock:
            try:
                sheet = self.get_google_sheet()
                existing_records = sheet.get_all_records()
                existing_serials = {str(rec.get('報名序號', '')).strip() for rec in existing_records}

                rows_to_append = []
                for row in data_list:
                    serial = str(row.get('報名序號', '')).strip()
                    if serial and serial not in existing_serials:
                        values = [row.get(col, '') for col in COLS_ORDER]
                        values.append(self.config.sheet_schema_version)
                        rows_to_append.append(values)
                        existing_serials.add(serial)

                if rows_to_append:
                    sheet.append_rows(rows_to_append, value_input_option='USER_ENTERED')
                return True, ''
            except Exception as e:
                return False, str(e)
