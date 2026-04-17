import re
from datetime import datetime
from threading import Lock
from typing import List, Tuple

from .config import AppConfig
from .models import Participant, RegistrationRow
from .sheet_service import SheetService

_build_lock = Lock()


class RegistrationService:
    def __init__(self, config: AppConfig, sheet_service: SheetService):
        self.config = config
        self.sheet_service = sheet_service

    @staticmethod
    def is_valid_date_text(date_text: str) -> bool:
        try:
            datetime.strptime(date_text, '%Y-%m-%d')
            return True
        except ValueError:
            return False

    def build_serial_code(self, timestamp_text: str, sequence_number: int) -> str:
        date_text = timestamp_text[:10].replace('-', '')
        return f'{date_text}{sequence_number:03d}'

    def validate_participant(self, person: Participant) -> Tuple[bool, str]:
        if not (2 <= len(person.name) <= 20):
            return False, '姓名長度需為 2 到 20 字'
        if person.gender not in ('男', '女'):
            return False, '性別格式不正確'
        if not self.is_valid_date_text(person.dob):
            return False, '出生年月日格式不正確'
        if not re.fullmatch(r'[A-Z][12]\d{8}', person.id_number):
            return False, '身分證字號格式不正確'
        if not re.fullmatch(r'09\d{8}', person.phone):
            return False, '電話號碼格式不正確'
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', person.email):
            return False, '電子郵件格式不正確'
        if person.ticket_type not in self.config.ticket_types:
            return False, '票種格式不正確'
        if person.food_types not in self.config.food_types:
            return False, '飲食選擇格式不正確'

        for key, qty in person.addons.items():
            if key not in self.config.addons:
                return False, '加購項目格式不正確'
            if not isinstance(qty, int) or qty < 0 or qty > 20:
                return False, '加購數量格式不正確'

        return True, ''

    def build_registration_rows(self, participants: List[Participant]) -> Tuple[bool, str, List[dict] | None, int | None]:
        remaining = self.sheet_service.remaining_seats()
        if len(participants) == 0:
            return False, '至少要有 1 位參加者', None, None
        if len(participants) > remaining:
            return False, f'剩餘座位不足，目前僅剩 {remaining} 席', None, None

        with _build_lock:
            current_count = self.sheet_service.get_registration_count()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_data: List[dict] = []
            total_amount = 0

            for i, person in enumerate(participants):
                ok, message = self.validate_participant(person)
                if not ok:
                    return False, message, None, None

                ticket_price = self.config.ticket_types.get(person.ticket_type, 0)

                addon_total = 0
                addon_quantities = {}
                for key, addon in self.config.addons.items():
                    qty = max(0, int(person.addons.get(key, 0)))
                    addon_quantities[f'加購_{key}'] = qty
                    addon_total += qty * int(addon['price'])

                person_total = ticket_price + addon_total
                total_amount += person_total
                serial_number = self.build_serial_code(timestamp, current_count + i + 1)

                row = RegistrationRow(
                    姓名=person.name,
                    性別=person.gender,
                    出生年月日=person.dob,
                    身分證字號=person.id_number,
                    電話號碼=person.phone,
                    電子郵件=person.email,
                    票種=person.ticket_type,
                    飲食選擇=person.food_types,
                    匯款銀行='',
                    匯款末四碼='',
                    備註='',
                    報名時間=timestamp,
                    金額=person_total,
                    報名序號=serial_number,
                    加購_easycard=addon_quantities.get('加購_easycard', 0),
                )
                new_data.append(row.to_dict())

            return True, '', new_data, total_amount
