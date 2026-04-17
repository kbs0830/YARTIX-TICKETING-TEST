import json
import os
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import Dict, List, Tuple

from urllib import parse as urlparse
from urllib import request as urlrequest

from .config import AppConfig
from .errors import E_PUSH_CONFIG, E_PUSH_SEND, E_SMTP_CONFIG, E_SMTP_SEND


class EmailService:
    def __init__(self, config: AppConfig):
        self.config = config

    @staticmethod
    def is_valid_email_address(email: str) -> bool:
        return bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', str(email).strip()))

    def append_failed_email_task(self, task: dict) -> None:
        try:
            with open(self.config.email_retry_queue_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(task, ensure_ascii=False) + '\n')
        except Exception:
            pass

    @staticmethod
    def _escape_html(text: str) -> str:
        return (
            str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;')
        )

    def send_email_smtp(self, to_emails: List[str], subject: str, body: str, html_body: str = '') -> Tuple[bool, str, str]:
        recipients = [email for email in to_emails if self.is_valid_email_address(email)]
        if not recipients:
            return False, E_SMTP_CONFIG, '缺少有效收件者 email'
        if not (self.config.smtp_username and self.config.smtp_app_password and self.config.smtp_from):
            return False, E_SMTP_CONFIG, 'SMTP 環境變數未完整設定'
        if self.config.smtp_app_password in ('你的16碼AppPassword', 'YOUR_16_CHAR_APP_PASSWORD'):
            return False, E_SMTP_CONFIG, 'SMTP_APP_PASSWORD 仍是範例文字，請改成 Gmail App Password（16 碼）'

        try:
            self.config.smtp_app_password.encode('ascii')
        except UnicodeEncodeError:
            return False, E_SMTP_CONFIG, 'SMTP_APP_PASSWORD 含非 ASCII 字元，請使用 Gmail App Password（16 碼英數）'

        message = EmailMessage()
        message['From'] = self.config.smtp_from
        message['To'] = ', '.join(recipients)
        message['Subject'] = subject
        message.set_content(body, charset='utf-8')
        if html_body:
            message.add_alternative(html_body, subtype='html', charset='utf-8')

        try:
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=20) as server:
                server.starttls()
                server.login(self.config.smtp_username, self.config.smtp_app_password)
                server.send_message(message)
            return True, '', ''
        except Exception as e:
            return False, E_SMTP_SEND, str(e)

    def build_payment_email_body(self, rows: List[Dict], total_amount: int, bank_info: Dict[str, str], line_group_link: str) -> str:
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

        easycard_cfg = self.config.addons.get('easycard', {'label': '悠遊卡', 'price': 0})
        easycard_label = easycard_cfg.get('label', '悠遊卡')
        easycard_price = to_int(easycard_cfg.get('price', 0))

        total_easycard_qty = 0
        participant_lines = []
        for index, row in enumerate(rows, start=1):
            easycard_qty = max(0, to_int(row.get('加購_easycard', 0)))
            total_easycard_qty += easycard_qty
            addon_text = (
                f"{easycard_label} {easycard_qty} 份（NT$ {easycard_qty * easycard_price}）"
                if easycard_qty > 0
                else '無'
            )
            serial_text = str(row.get('報名序號', '')).strip() or '無'
            participant_lines.append(
                f"【參加者{index}】\n"
                f"姓名：{row.get('姓名', '')}\n"
                f"報名序號：{serial_text}\n"
                f"票種：{row.get('票種', '')}\n"
                f"飲食：{row.get('飲食選擇', '')}\n"
                f"加購項目：{addon_text}\n"
                f"小計：NT$ {row.get('金額', 0)}"
            )

        participants_text = '\n'.join(participant_lines)
        account_name = '台灣鐵道文化意象 TWRIC'

        return (
            '您好，\n\n'
            '感謝您的報名！您的報名手續已初步完成，為保留您的名額，請於期限內完成繳費。\n\n'
            '【付款資訊】\n'
            f"銀行：{bank_info['銀行']}\n"
            f"帳號：{bank_info['帳號']}\n"
            f"戶名：{account_name}\n"
            f"應付總金額：NT$ {total_amount}\n\n"
            '【重要提醒：匯款後請務必回報】\n'
            '完成匯款後，請透過以下任一方式回報，並提供「報名序號」與「帳號後五碼」，以便快速對帳：\n'
            '1. LINE 回報：加入下方活動 LINE 群組後，直接私訊管理員。\n'
            '2. Email 回報：直接回覆本信件。\n'
            '（待款項查證後，我們將寄送付款成功通知，請耐心等候。）\n\n'
            '【專屬 LINE 群組】\n'
            '若有公告資料會在群組，或是回傳匯款明細也可以找到主辦方私訊，方便查帳。\n'
            f"LINE 群組：{line_group_link}\n\n"
            f"【報名明細確認（共 {len(rows)} 位）】\n\n{participants_text}\n\n"
            '若您對訂單有任何疑問，歡迎透過 LINE 群組或回覆本信件與我們聯繫。\n'
            '期待在活動中與您相見！\n\n'
            '台灣鐵道文化意象 TWRIC 敬上'
        )

    def build_payment_email_html(self, rows: List[Dict], total_amount: int, bank_info: Dict[str, str], line_group_link: str) -> str:
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

        easycard_cfg = self.config.addons.get('easycard', {'label': '悠遊卡', 'price': 0})
        easycard_label = easycard_cfg.get('label', '悠遊卡')
        easycard_price = to_int(easycard_cfg.get('price', 0))

        total_easycard_qty = 0
        participant_html_blocks = []
        for index, row in enumerate(rows, start=1):
            easycard_qty = max(0, to_int(row.get('加購_easycard', 0)))
            total_easycard_qty += easycard_qty
            addon_text = (
                f"{easycard_label} {easycard_qty} 份（NT$ {easycard_qty * easycard_price}）"
                if easycard_qty > 0
                else '無'
            )

            participant_html_blocks.append(
                (
                    '<div class="participant">'
                    f"<p class=\"participant-title\">【參加者{index}】</p>"
                    f"<div>姓名：{self._escape_html(row.get('姓名', ''))}</div>"
                    f"<div>報名序號：{self._escape_html(row.get('報名序號', ''))}</div>"
                    f"<div>票種：{self._escape_html(row.get('票種', ''))}</div>"
                    f"<div>飲食：{self._escape_html(row.get('飲食選擇', ''))}</div>"
                    f"<div>加購項目：{self._escape_html(addon_text)}</div>"
                    f"<div>小計：NT$ {self._escape_html(row.get('金額', 0))}</div>"
                    '</div>'
                )
            )

        account_name = '台灣鐵道文化意象 TWRIC'

        return (
            '<!doctype html>'
            '<html>'
            '<head>'
            '<meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<style>'
            'body{margin:0;padding:0;background:#f8fafc;color:#1f2937;font-family:Arial,"Noto Sans TC",sans-serif;line-height:1.7;}'
            '.wrap{max-width:680px;margin:0 auto;padding:14px;}'
            '.card{background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:14px;}'
            '.intro{margin:0 0 10px 0;font-size:16px;}'
            '.section{margin:14px 0 0 0;}'
            '.section-title{margin:0 0 8px 0;font-size:18px;font-weight:800;color:#0f172a;}'
            '.pay-box{padding:10px 12px;border:1px solid #dbeafe;border-radius:10px;background:#f8fbff;}'
            '.row{margin:4px 0;font-size:15px;}'
            '.strong{font-weight:800;}'
            '.pay-blue{color:#1d4ed8;}'
            '.total{margin:10px 0 2px 0;font-size:22px;font-weight:900;color:#1d4ed8;line-height:1.25;}'
            '.hint{margin:8px 0 0 0;color:#334155;font-size:14px;}'
            '.report-list{margin:8px 0 0 20px;padding:0;}'
            '.report-list li{margin:4px 0;}'
            '.line-link{display:inline-block;margin-top:4px;color:#0f5ac4;font-weight:700;word-break:break-all;}'
            '.participant{margin:10px 0;padding:10px;border:1px solid #e2e8f0;border-radius:10px;background:#fcfdff;}'
            '.participant-title{margin:0 0 6px 0;font-size:15px;font-weight:800;color:#0f172a;}'
            '.closing{margin-top:14px;font-size:14px;color:#1f2937;}'
            '@media screen and (max-width:480px){'
            '.wrap{padding:10px;}'
            '.card{padding:12px;}'
            '.intro{font-size:16px;}'
            '.row{font-size:14px;}'
            '.total{font-size:19px;}'
            '}'
            '</style>'
            '</head>'
            '<body>'
            '<div class="wrap">'
            '<div class="card">'
            '<p class="intro">您好，</p>'
            '<p class="intro">感謝您的報名！您的報名手續已初步完成，為保留您的名額，請於期限內完成繳費。</p>'
            '<div class="section">'
            '<h3 class="section-title">付款資訊</h3>'
            '<div class="pay-box">'
            f"<p class=\"row strong\">銀行：{self._escape_html(bank_info['銀行'])}</p>"
            f"<p class=\"row strong\">帳號：{self._escape_html(bank_info['帳號'])}</p>"
            f"<p class=\"row strong\">戶名：{self._escape_html(account_name)}</p>"
            f"<p class=\"total\">應付總金額：NT$ {total_amount}</p>"
            '</div>'
            '<div class="section">'
            '<h3 class="section-title">【重要提醒：匯款後請務必回報】</h3>'
            '<p class="row">完成匯款後，請透過以下任一方式回報，並提供「報名序號」與「帳號後五碼」，以便快速對帳：</p>'
            '<ol class="report-list">'
            '<li><strong>LINE 回報</strong>：加入下方活動 LINE 群組後，直接私訊管理員。</li>'
            '<li><strong>Email 回報</strong>：直接回覆本信件。</li>'
            '</ol>'
            '<p class="hint">（待款項查證後，我們將寄送付款成功通知，請耐心等候。）</p>'
            '</div>'
            '<div class="section">'
            '<h3 class="section-title">專屬 LINE 群組</h3>'
            '<p class="row">若有公告資料會在群組，或是回傳匯款明細也可以找到主辦方私訊，方便查帳。</p>'
            f"<a class=\"line-link\" href=\"{self._escape_html(line_group_link)}\" target=\"_blank\" rel=\"noreferrer\">點此加入活動專屬 LINE 群組</a>"
            '</div>'
            '<div class="section">'
            f"<h3 class=\"section-title\">報名明細確認（共 {len(rows)} 位）</h3>"
            f"{''.join(participant_html_blocks)}"
            '</div>'
            '<p class="closing">若您對訂單有任何疑問，歡迎透過 LINE 群組或回覆本信件與我們聯繫。<br>期待在活動中與您相見！<br><br>台灣鐵道文化意象 TWRIC 敬上</p>'
            '</div>'
            '</div>'
            '</body>'
            '</html>'
        )

    def send_payment_email(self, rows: List[Dict], total_amount: int, bank_info: Dict[str, str], line_group_link: str) -> Tuple[bool, str, str]:
        recipients = []
        for row in rows:
            email = str(row.get('電子郵件', '')).strip()
            if email and email not in recipients:
                recipients.append(email)

        subject = '【台灣鐵道文化意象 TWRIC】您的報名已完成！請查閱付款資訊與明細'
        body = self.build_payment_email_body(rows, total_amount, bank_info, line_group_link)
        html_body = self.build_payment_email_html(rows, total_amount, bank_info, line_group_link)
        ok, err_code, message = self.send_email_smtp(recipients, subject, body, html_body=html_body)
        if ok:
            return True, '', ''

        self.append_failed_email_task({
            'type': 'payment_info',
            'created_at': datetime.now().isoformat(timespec='seconds'),
            'to_emails': recipients,
            'subject': subject,
            'body': body,
            'html_body': html_body,
            'error': message,
            'error_code': err_code,
            'serial_numbers': [row.get('報名序號', '') for row in rows],
        })
        return False, err_code, message

    def send_push_notification(self, message: str) -> Tuple[bool, str, str]:
        if not self.config.push_enabled:
            return True, '', ''

        provider = self.config.push_provider
        if provider == 'gmail':
            if not self.config.push_target_email:
                return False, E_PUSH_CONFIG, 'PUSH_TARGET_EMAIL 未設定'
            return self.send_email_smtp([self.config.push_target_email], '報名成功通知', message)

        if provider == 'telegram':
            if not self.config.push_telegram_bot_token or not self.config.push_telegram_chat_id:
                return False, E_PUSH_CONFIG, 'Telegram 推送參數未設定'
            api_url = f"https://api.telegram.org/bot{self.config.push_telegram_bot_token}/sendMessage"
            payload = urlparse.urlencode({
                'chat_id': self.config.push_telegram_chat_id,
                'text': message,
            }).encode('utf-8')
            req = urlrequest.Request(api_url, data=payload)
            try:
                with urlrequest.urlopen(req, timeout=15) as resp:
                    if resp.status >= 400:
                        return False, E_PUSH_SEND, f'Telegram HTTP {resp.status}'
                return True, '', ''
            except Exception as e:
                return False, E_PUSH_SEND, str(e)

        if provider == 'line':
            if not self.config.push_line_notify_token:
                return False, E_PUSH_CONFIG, 'PUSH_LINE_NOTIFY_TOKEN 未設定'
            payload = urlparse.urlencode({'message': message}).encode('utf-8')
            req = urlrequest.Request(
                'https://notify-api.line.me/api/notify',
                data=payload,
                headers={'Authorization': f'Bearer {self.config.push_line_notify_token}'},
            )
            try:
                with urlrequest.urlopen(req, timeout=15) as resp:
                    if resp.status >= 400:
                        return False, E_PUSH_SEND, f'LINE HTTP {resp.status}'
                return True, '', ''
            except Exception as e:
                return False, E_PUSH_SEND, str(e)

        return False, E_PUSH_CONFIG, 'PUSH_PROVIDER 未設定或不支援'

    def retry_email_queue(self) -> Tuple[int, int]:
        if not self.config.email_retry_queue_file:
            return 0, 0
        if not os.path.exists(self.config.email_retry_queue_file):
            return 0, 0

        resent = 0
        remain_tasks = []
        with open(self.config.email_retry_queue_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        for line in lines:
            try:
                task = json.loads(line)
                ok, err_code, err = self.send_email_smtp(
                    task.get('to_emails', []),
                    task.get('subject', ''),
                    task.get('body', ''),
                    html_body=task.get('html_body', ''),
                )
                if ok:
                    resent += 1
                else:
                    task['error'] = err
                    task['error_code'] = err_code
                    remain_tasks.append(task)
            except Exception as e:
                remain_tasks.append({'type': 'unknown', 'error': str(e), 'raw': line})

        with open(self.config.email_retry_queue_file, 'w', encoding='utf-8') as f:
            for task in remain_tasks:
                f.write(json.dumps(task, ensure_ascii=False) + '\n')

        return resent, len(remain_tasks)


def build_push_message(rows: List[Dict]) -> str:
    lines = ['報名成功通知']
    for row in rows:
        lines.append(
            f"姓名:{row.get('姓名', '')} 票種:{row.get('票種', '')} 金額:{row.get('金額', 0)} 序號:{row.get('報名序號', '')} 匯款末四碼:{row.get('匯款末四碼', '')}"
        )
    return '\n'.join(lines)
