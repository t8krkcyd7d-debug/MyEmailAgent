"""
email_client.py - 封装 IMAP（收）和 SMTP（发）的邮件操作

Python 标准库提供了 imaplib 和 smtplib，不需要额外安装。
我们封装成一个类，所有敏感信息从环境变量读取。
"""

import imaplib          # IMAP4 协议客户端（接收邮件）
import smtplib          # SMTP 协议客户端（发送邮件）
import email            # 解析邮件格式（RFC 822/MIME）
from email.mime.text import MIMEText          # 构造纯文本邮件
from email.mime.multipart import MIMEMultipart # 构造多部分邮件
from email.header import Header, decode_header # 处理编码（中文等）
from email.utils import parsedate_to_datetime
from typing import List, Dict, Optional
from datetime import datetime
import os
import json
import re
import ssl               # SSL/TLS 加密连接


ENTERPRISE_SENDERS = (
    "onedrive", "wolfram", "microsoft", "office365", "dropbox",
    "google drive", "icloud", "adobe", "notion", "zoom", "github",
)
ACCOUNT_ACTION_WORDS = (
    "续费", "到期", "过期", "账号验证", "账户验证", "身份验证", "安全验证",
    "renew", "renewal", "expire", "expiration", "verify", "verification",
)


def urgency_from_subject(subject: str, from_addr: str = "") -> str:
    """Use the same business meaning as the AI rule for instant list labels."""
    text = (subject or "").lower()
    if re.match(r"^\s*[<＜]\s*广告\s*[>＞]", text):
        return "低"
    sender = (from_addr or "").lower()
    if any(name in sender for name in ENTERPRISE_SENDERS):
        if any(word in text for word in ACCOUNT_ACTION_WORDS):
            return "紧急" if any(word in text for word in ("到期", "过期", "expire", "expiration")) else "普通"
        return "低"
    urgent_words = ("紧急", "立即", "马上", "故障", "宕机", "事故", "安全", "截止", "urgent", "asap")
    low_words = ("广告", "促销", "优惠", "订阅", "newsletter", "推广")
    if any(word in text for word in urgent_words):
        return "紧急"
    if any(word in text for word in low_words):
        return "低"
    return "普通"


class EmailClient:
    """
    邮件客户端类，封装所有底层网络操作。

    类比 C++ 中一个封装了 libcurl 和 libetpan 的类，
    对外提供简单的接口。
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        构造函数：从环境变量读取配置。
        如果配置不完整，抛出异常（类似 C++ 构造函数中 assert）。
        """
        # 从 os.environ 读取（.env 已由 python-dotenv 加载）
        config = config or {}
        self.account_id = str(config.get("id") or "default")
        self.label = str(config.get("label") or config.get("address") or os.getenv("EMAIL_ADDRESS", "我的邮箱"))
        self.imap_server = config.get("imap_server") or os.getenv("EMAIL_IMAP_SERVER")
        self.imap_port = int(config.get("imap_port") or os.getenv("EMAIL_IMAP_PORT", 993))
        self.smtp_server = config.get("smtp_server") or os.getenv("EMAIL_SMTP_SERVER")
        self.smtp_port = int(config.get("smtp_port") or os.getenv("EMAIL_SMTP_PORT", 465))
        self.email_address = config.get("address") or os.getenv("EMAIL_ADDRESS")
        self.email_password = config.get("password") or os.getenv("EMAIL_PASSWORD")  # 授权码
        self.trash_folder = config.get("trash_folder") or os.getenv('EMAIL_TRASH_FOLDER', 'Trash')

        # 验证必填项是否存在
        if not all([self.imap_server, self.smtp_server,
                    self.email_address, self.email_password]):
            raise ValueError(
                "邮件配置不完整，请检查 .env 中的 EMAIL_* 变量"
            )

    # ============================================================
    # 1. IMAP 接收邮件部分
    # ============================================================

    def connect_imap(self) -> imaplib.IMAP4_SSL:
        """
        建立 IMAP SSL 安全连接，并登录。

        返回：
            imaplib.IMAP4_SSL 已认证的连接对象

        注意：如果连接失败，会抛出异常（类似 C++ 抛出 std::runtime_error）。
        """
        # 创建 SSL 上下文，强制验证服务器证书（安全）
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        # 建立 SSL 连接，超时 30 秒
        conn = imaplib.IMAP4_SSL(
            host=self.imap_server,
            port=self.imap_port,
            timeout=30,
            ssl_context=context
        )

        # 登录
        conn.login(self.email_address, self.email_password)
        return conn

    def fetch_unread_emails(self, limit: int = 10) -> List[Dict]:
        """
        获取收件箱中的未读邮件。

        参数：
            limit: 最多返回多少封（默认 10）

        返回：
            List[Dict]：每封邮件包含 id, from, subject, body, date

        """
        conn = self.connect_imap()   # 打开连接
        try:
            # 选择收件箱（只读模式，防止误操作）
            conn.select('INBOX', readonly=True)

            # 搜索未读邮件（UNSEEN 是 IMAP 关键词）
            status, search_data = conn.search(None, 'UNSEEN')
            if status != 'OK':
                return []

            # search_data[0] 是空格分隔的邮件 ID 字符串
            email_ids = search_data[0].split()
            if not email_ids:
                return []

            # 取最近的 limit 封（ID 越大越新）
            # Newest first, so the workflow analyses the latest unread email.
            email_ids = reversed(email_ids[-limit:])

            emails = []
            for eid in email_ids:
                # 获取邮件原始数据（RFC822 格式）
                status, msg_data = conn.fetch(eid, '(RFC822)')
                if status != 'OK':
                    continue

                # 解析邮件为 email.message.Message 对象
                msg = email.message_from_bytes(msg_data[0][1])

                # 提取字段（可能编码）
                subject = self._decode_header(msg.get('Subject', '无主题'))
                from_addr = self._decode_header(msg.get('From', '未知发件人'))
                date = msg.get('Date', '')

                # 提取正文（纯文本或 HTML）
                body = self._get_email_body(msg)

                emails.append({
                    'id': int(eid),
                    'from': from_addr,
                    'subject': subject,
                    'body': body,
                    'date': date,
                })

            return emails

        finally:
            # 无论是否异常，都要关闭连接（类似 C++ 的 RAII）
            try:
                conn.close()
            finally:
                conn.logout()

    def fetch_email_by_id(self, email_id: int) -> Optional[Dict]:
        """
        根据邮件 ID 获取单封邮件的完整内容（包括正文）。

        参数：
            email_id: 邮件 ID

        返回：
            Dict 或 None（如果不存在）
        """
        conn = self.connect_imap()
        try:
            conn.select('INBOX', readonly=True)

            status, msg_data = conn.fetch(str(email_id), '(RFC822)')
            if status != 'OK' or not msg_data[0]:
                return None

            msg = email.message_from_bytes(msg_data[0][1])

            return {
                'from': self._decode_header(msg.get('From', '未知发件人')),
                'subject': self._decode_header(msg.get('Subject', '无主题')),
                'body': self._get_email_body(msg),
                'date': msg.get('Date', ''),
            }

        finally:
            try:
                conn.close()
            finally:
                conn.logout()

    # ---------- 辅助函数 ----------
    def _decode_header(self, header_value: str) -> str:
        """
        解码邮件头（处理 =?UTF-8?B?xxxx?= 这类编码）

        参数：
            header_value: 原始字符串

        返回：
            解码后的 Unicode 字符串
        """
        if not header_value:
            return ""

        # decode_header 返回 list of (bytes/str, encoding)
        decoded_parts = decode_header(header_value)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                # 如果有 encoding 则用该编码，否则用 UTF-8
                charset = encoding or 'utf-8'
                try:
                    result.append(part.decode(charset, errors='ignore'))
                except:
                    result.append(part.decode('utf-8', errors='ignore'))
            else:
                result.append(str(part))
        return ''.join(result)

    def _get_email_body(self, msg) -> str:
        """
        从 email.message.Message 对象中提取纯文本正文。

        MIME 邮件可能包含多个部分（文本+附件），
        我们优先取 text/plain，其次取 text/html。
        """
        if msg.is_multipart():
            # 遍历所有子部分
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        return payload.decode(charset, errors='ignore')
                    except:
                        return payload.decode('utf-8', errors='ignore')
            # 如果没找到纯文本，尝试 HTML
            for part in msg.walk():
                if part.get_content_type() == 'text/html':
                    payload = part.get_payload(decode=True)
                    return payload.decode('utf-8', errors='ignore')
        else:
            # 非 multipart（纯文本邮件）
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                try:
                    return payload.decode(charset, errors='ignore')
                except:
                    return payload.decode('utf-8', errors='ignore')
        return "（无法解析邮件正文）"

    def list_emails(self, folder: str = "INBOX", limit: int = 50,
                    query: str = "") -> List[Dict]:
        """Return newest messages from a folder without changing read state."""
        conn = self.connect_imap()
        try:
            status, _ = conn.select(folder, readonly=True)
            if status != 'OK':
                raise ValueError(f"无法打开邮件夹：{folder}")
            # Start with recent mail so a large mailbox still opens quickly.
            # Fall back to ALL only for an account with no mail in three years.
            since = f"01-Jan-{datetime.now().year - 2}"
            status, data = conn.search(None, 'SINCE', since)
            if status != 'OK':
                return []
            ids = data[0].split()
            if not ids:
                status, data = conn.search(None, 'ALL')
                if status != 'OK':
                    return []
                ids = data[0].split()
            result = []
            # IMAP sequence numbers are not guaranteed to follow message dates.
            # Fetch all headers in batches, sort by Date, and only then apply limit.
            for offset in range(0, len(ids), 500):
                sequence_set = b','.join(ids[offset:offset + 500])
                status, msg_data = conn.fetch(sequence_set, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)] FLAGS)')
                if status != 'OK':
                    continue
                for part in msg_data:
                    if not isinstance(part, tuple):
                        continue
                    raw_meta, raw_message = part
                    id_match = re.match(rb'(\d+)', raw_meta)
                    if not id_match:
                        continue
                    msg = email.message_from_bytes(raw_message)
                    flags = raw_meta.decode(errors='ignore')
                    decoded_subject = self._decode_header(msg.get('Subject', '无主题'))
                    decoded_from = self._decode_header(msg.get('From', '未知发件人'))
                    if query.strip() and query.strip().casefold() not in f"{decoded_from} {decoded_subject}".casefold():
                        continue
                    result.append({
                        'id': int(id_match.group(1)),
                        'from': decoded_from,
                        'subject': decoded_subject,
                        'date': msg.get('Date', ''),
                        'is_read': '\\Seen' in flags,
                        'is_starred': '\\Flagged' in flags,
                        'urgency': urgency_from_subject(decoded_subject, decoded_from),
                    })
            def message_time(item: Dict):
                try:
                    value = parsedate_to_datetime(item.get('date', ''))
                    # A naive and an aware datetime cannot be compared directly.
                    return value.timestamp()
                except (TypeError, ValueError, OverflowError):
                    return 0

            return sorted(result, key=message_time, reverse=True)[:limit]
        finally:
            try:
                conn.close()
            finally:
                conn.logout()

    def get_email(self, email_id: int, folder: str = "INBOX") -> Optional[Dict]:
        """Return a full message, preserving its current read state."""
        conn = self.connect_imap()
        try:
            status, _ = conn.select(folder, readonly=True)
            if status != 'OK':
                return None
            status, msg_data = conn.fetch(str(email_id), '(BODY.PEEK[] FLAGS)')
            if status != 'OK' or not msg_data or not isinstance(msg_data[0], tuple):
                return None
            raw_meta, raw_message = msg_data[0]
            msg = email.message_from_bytes(raw_message)
            flags = raw_meta.decode(errors='ignore')
            return {
                'id': email_id,
                'from': self._decode_header(msg.get('From', '未知发件人')),
                'to': self._decode_header(msg.get('To', '')),
                'subject': self._decode_header(msg.get('Subject', '无主题')),
                'date': msg.get('Date', ''),
                'body': self._get_email_body(msg),
                'is_read': '\\Seen' in flags,
                'is_starred': '\\Flagged' in flags,
            }
        finally:
            try:
                conn.close()
            finally:
                conn.logout()

    def update_email(self, email_id: int, action: str, folder: str = "INBOX") -> None:
        """Apply a safe, explicit mailbox action to one message."""
        conn = self.connect_imap()
        try:
            status, _ = conn.select(folder, readonly=False)
            if status != 'OK':
                raise ValueError(f"无法打开邮件夹：{folder}")
            eid = str(email_id)
            if action in {'read', 'unread', 'star', 'unstar'}:
                flag = {'read': '\\Seen', 'unread': '\\Seen', 'star': '\\Flagged', 'unstar': '\\Flagged'}[action]
                operation = '+FLAGS' if action in {'read', 'star'} else '-FLAGS'
                status, _ = conn.store(eid, operation, flag)
            elif action == 'trash':
                target = self.trash_folder
                status, _ = conn.copy(eid, target)
                if status == 'OK':
                    conn.store(eid, '+FLAGS', '\\Deleted')
                    conn.expunge()
            elif action == 'delete':
                status, _ = conn.store(eid, '+FLAGS', '\\Deleted')
                if status == 'OK':
                    conn.expunge()
            else:
                raise ValueError("不支持的邮件操作")
            if status != 'OK':
                raise RuntimeError("邮箱服务器未能完成该操作")
        finally:
            try:
                conn.close()
            finally:
                conn.logout()

    # ============================================================
    # 2. SMTP 发送邮件部分
    # ============================================================

    def send_email(self, to: str, subject: str, body: str) -> bool:
        """
        通过 SMTP 发送邮件。

        参数：
            to: 收件人地址
            subject: 主题
            body: 正文

        返回：
            True 表示成功，False 表示失败
        """
        try:
            # 构造 MIME 邮件
            msg = MIMEMultipart()
            msg['From'] = self.email_address
            msg['To'] = to
            msg['Subject'] = Header(subject, 'utf-8')

            # 添加纯文本正文
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # Port 465 normally uses implicit TLS; 587 normally uses STARTTLS.
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=30) as server:
                    server.login(self.email_address, self.email_password)
                    server.sendmail(self.email_address, [to], msg.as_string())
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                    server.starttls(context=ssl.create_default_context())
                    server.login(self.email_address, self.email_password)
                    server.sendmail(self.email_address, [to], msg.as_string())

            return True

        except Exception as e:
            print(f"发送邮件失败: {e}")
            return False


# ---------- 单例模式：全局只创建一个客户端实例 ----------
_email_clients = None


def get_email_accounts() -> Dict[str, EmailClient]:
    """Load multiple authorization-code accounts, with legacy env fallback."""
    global _email_clients
    if _email_clients is not None:
        return _email_clients
    raw = os.getenv("EMAIL_ACCOUNTS_JSON", "").strip()
    configs = json.loads(raw) if raw else []
    if not configs:
        configs = [{"id": "default", "label": "我的邮箱"}]
    _email_clients = {str(c.get("id") or f"account{index + 1}"): EmailClient(c)
                      for index, c in enumerate(configs)}
    return _email_clients

def get_email_client(account_id: Optional[str] = None) -> EmailClient:
    """
    获取全局唯一的 EmailClient 实例。
    第一次调用时创建，之后复用。

    这类似于 C++ 中的单例模式：
    static EmailClient& getInstance() { static EmailClient instance; return instance; }
    """
    accounts = get_email_accounts()
    if account_id and account_id not in accounts:
        raise ValueError("没有找到这个邮箱账号")
    return accounts[account_id] if account_id else next(iter(accounts.values()))
