from config import load_config
from email_service import EmailService
from models import Participant
from registration_service import RegistrationService


class FakeSheetService:
    def __init__(self, remaining=10, count=3):
        self._remaining = remaining
        self._count = count

    def remaining_seats(self):
        return self._remaining

    def get_registration_count(self):
        return self._count


def test_validate_participant_ok():
    cfg = load_config()
    service = RegistrationService(cfg, FakeSheetService())
    p = Participant.from_dict({
        'name': '王小明',
        'gender': '男',
        'dob': '2000-01-01',
        'id_number': 'A123456789',
        'phone': '0912345678',
        'email': 'test@example.com',
        'ticket_type': '一般套票',
        'food_types': '葷',
        'addons': {'easycard': 1},
    })

    ok, message = service.validate_participant(p)
    assert ok is True
    assert message == ''


def test_build_registration_rows_total_and_serial():
    cfg = load_config()
    service = RegistrationService(cfg, FakeSheetService(remaining=10, count=5))
    people = [
        Participant.from_dict({
            'name': '王小明',
            'gender': '男',
            'dob': '2000-01-01',
            'id_number': 'A123456789',
            'phone': '0912345678',
            'email': 'a@example.com',
            'ticket_type': '一般套票',
            'food_types': '葷',
            'addons': {'easycard': 1},
        }),
        Participant.from_dict({
            'name': '李小華',
            'gender': '女',
            'dob': '2001-01-01',
            'id_number': 'B223456789',
            'phone': '0922345678',
            'email': 'b@example.com',
            'ticket_type': '優待套票(12歲以下/65歲以上)',
            'food_types': '素',
            'addons': {'easycard': 0},
        }),
    ]

    ok, message, rows, total_amount = service.build_registration_rows(people)
    assert ok is True
    assert message == ''
    assert rows is not None
    assert len(rows) == 2
    assert total_amount == 5400
    assert rows[0]['報名序號'].isdigit()
    assert rows[1]['報名序號'].isdigit()


def test_build_payment_email_body_contains_details():
    cfg = load_config()
    email_service = EmailService(cfg)
    rows = [
        {
            '姓名': '王小明',
            '性別': '男',
            '出生年月日': '2000-01-01',
            '身分證字號': 'A123456789',
            '電話號碼': '0912345678',
            '電子郵件': 'a@example.com',
            '票種': '一般套票',
            '飲食選擇': '葷',
            '加購_easycard': 1,
            '金額': 2900,
            '報名序號': '20260417001',
        }
    ]

    body = email_service.build_payment_email_body(rows, 2900, cfg.bank_info, cfg.line_group_link)
    assert '總金額：NT$ 2900' in body
    assert '報名序號：20260417001' in body
    assert '加購：悠遊卡 1 份（NT$ 300）' in body
