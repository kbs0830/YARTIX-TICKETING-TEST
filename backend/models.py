from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict


@dataclass
class Participant:
    name: str
    gender: str
    dob: str
    id_number: str
    phone: str
    email: str
    ticket_type: str
    food_types: str
    addons: Dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> 'Participant':
        addons = data.get('addons', {})
        return cls(
            name=str(data.get('name', '')).strip(),
            gender=str(data.get('gender', '')).strip(),
            dob=str(data.get('dob', '')).strip(),
            id_number=str(data.get('id_number', '')).strip().upper(),
            phone=str(data.get('phone', '')).strip(),
            email=str(data.get('email', '')).strip(),
            ticket_type=str(data.get('ticket_type', '')).strip(),
            food_types=str(data.get('food_types', '')).strip(),
            addons=addons if isinstance(addons, dict) else {},
        )


@dataclass
class RegistrationRow:
    姓名: str
    性別: str
    出生年月日: str
    身分證字號: str
    電話號碼: str
    電子郵件: str
    票種: str
    飲食選擇: str
    匯款銀行: str
    匯款末四碼: str
    備註: str
    報名時間: str
    金額: int
    報名序號: str
    加購_easycard: int = 0

    def to_dict(self) -> dict:
        return {
            '姓名': self.姓名,
            '性別': self.性別,
            '出生年月日': self.出生年月日,
            '身分證字號': self.身分證字號,
            '電話號碼': self.電話號碼,
            '電子郵件': self.電子郵件,
            '票種': self.票種,
            '飲食選擇': self.飲食選擇,
            '匯款銀行': self.匯款銀行,
            '匯款末四碼': self.匯款末四碼,
            '備註': self.備註,
            '報名時間': self.報名時間,
            '加購_easycard': self.加購_easycard,
            '金額': self.金額,
            '報名序號': self.報名序號,
        }


def now_timestamp_text() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
