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
        for row in rows:
            easycard_qty = max(0, to_int(row.get('加購_easycard', 0)))
            total_easycard_qty += easycard_qty
            addon_text = (
                f"{easycard_label} {easycard_qty} 份（NT$ {easycard_qty * easycard_price}）"
                if easycard_qty > 0
                else '無'
            )
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

        return (
            '您好，您的報名已完成，以下為付款資訊：\n\n'
            f"報名人數：{len(rows)}\n"
            f"銀行：{bank_info['銀行']}\n"
            f"帳號：{bank_info['帳號']}\n"
            '待款項查證後會郵寄通知付款成功，請耐心等待。\n'
            f"戶名：{bank_info['戶名']}\n"
            f"總金額：NT$ {total_amount}\n"
            f"{easycard_summary}\n"
            f"報名序號：{', '.join(serials) if serials else '無'}\n"
            f"付款期限：{self.config.payment_deadline_text}\n\n"
            f'參加者完整明細：\n{participants_text}\n\n'
            f'LINE 群組連結：{line_group_link}\n\n'
            '提醒：若匯款後需回報，請於信件主旨附上報名序號。\n'
            '若有疑問請回覆本信，謝謝。'
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
        for row in rows:
            easycard_qty = max(0, to_int(row.get('加購_easycard', 0)))
            total_easycard_qty += easycard_qty
            addon_text = (
                f"{easycard_label} {easycard_qty} 份（NT$ {easycard_qty * easycard_price}）"
                if easycard_qty > 0
                else '無'
            )

            participant_html_blocks.append(
                (
                    '<li style="margin-bottom:12px;">'
                    f"<div>姓名：{self._escape_html(row.get('姓名', ''))}</div>"
                    f"<div>報名序號：{self._escape_html(row.get('報名序號', ''))}</div>"
                    f"<div>身分證：{self._escape_html(mask_id_number(row.get('身分證字號', '')))}</div>"
                    f"<div>出生日期：{self._escape_html(row.get('出生年月日', ''))}</div>"
                    f"<div>聯絡電話：{self._escape_html(row.get('電話號碼', ''))}</div>"
                    f"<div>Email：{self._escape_html(row.get('電子郵件', ''))}</div>"
                    f"<div>票種：{self._escape_html(row.get('票種', ''))}</div>"
                    f"<div>飲食：{self._escape_html(row.get('飲食選擇', ''))}</div>"
                    f"<div>加購：{self._escape_html(addon_text)}</div>"
                    f"<div>小計：NT$ {self._escape_html(row.get('金額', 0))}</div>"
                    '</li>'
                )
            )

        easycard_summary = (
            f"{easycard_label}：有（共 {total_easycard_qty} 張，NT$ {total_easycard_qty * easycard_price}）"
            if total_easycard_qty > 0
            else f"{easycard_label}：無"
        )

        return (
            '<!doctype html>'
            '<html>'
            '<head>'
            '<meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<style>'
            'body{margin:0;padding:0;background:#f8fafc;color:#1f2937;font-family:Arial,"Noto Sans TC",sans-serif;line-height:1.65;}'
            '.wrap{max-width:680px;margin:0 auto;padding:14px;}'
            '.card{background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:14px;}'
            '.row{margin:6px 0;font-size:15px;}'
            '.total{margin:14px 0 8px 0;font-size:34px;font-weight:900;color:#b91c1c;line-height:1.25;}'
            '.sub-title{margin:16px 0 8px 0;font-size:18px;font-weight:800;}'
            '.note{margin:8px 0;color:#0f172a;}'
            '.list{padding-left:18px;margin:0;}'
            '.list li{margin-bottom:12px;}'
            '@media screen and (max-width:480px){'
            '.wrap{padding:10px;}'
            '.card{padding:12px;}'
            '.row{font-size:14px;}'
            '.sub-title{font-size:16px;}'
            '.total{font-size:28px;}'
            '}'
            '</style>'
            '</head>'
            '<body>'
            '<div class="wrap">'
            '<div class="card">'
            '<h2 style="margin:0 0 12px 0;font-size:22px;">您好，您的報名已完成，以下為付款資訊：</h2>'
            f"<p class=\"row\">報名人數：{len(rows)}</p>"
            f"<p class=\"row\">銀行：{self._escape_html(bank_info['銀行'])}</p>"
            f"<p class=\"row\">帳號：{self._escape_html(bank_info['帳號'])}</p>"
            '<p class="note">待款項查證後會郵寄通知付款成功，請耐心等待。</p>'
            f"<p class=\"row\">戶名：{self._escape_html(bank_info['戶名'])}</p>"
            f"<p class=\"total\">總金額：NT$ {total_amount}</p>"
            f"<p class=\"row\">{self._escape_html(easycard_summary)}</p>"
            f"<p class=\"row\">報名序號：{self._escape_html(', '.join(serials) if serials else '無')}</p>"
            f"<p class=\"row\">付款期限：{self._escape_html(self.config.payment_deadline_text)}</p>"
            '<h3 class="sub-title">參加者完整明細：</h3>'
            f"<ul class=\"list\">{''.join(participant_html_blocks)}</ul>"
            f"<p class=\"row\" style=\"margin-top:16px;\">LINE 群組連結：<a href=\"{self._escape_html(line_group_link)}\" target=\"_blank\" rel=\"noreferrer\">{self._escape_html(line_group_link)}</a></p>"
            '<p class="row">提醒：若匯款後需回報，請於信件主旨附上報名序號。</p>'
            '<p class="row">若有疑問請回覆本信，謝謝。</p>'
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

        subject = '【春映洄瀾，拾光】普悠瑪專列，付款資訊通知'
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
