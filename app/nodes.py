"""LangGraph nodes for fetching and analysing email."""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from html import unescape
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.email_client import get_email_client
from app.email_client import ACCOUNT_ACTION_WORDS, ENTERPRISE_SENDERS

VALID_URGENCIES = {"紧急", "普通", "低"}
MAX_EMAIL_CHARS = int(os.getenv("MAX_EMAIL_CHARS", "12000"))


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """Create the client lazily, after ``load_dotenv`` has run."""
    provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
    common = {
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
        "max_tokens": int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "600")),
        "timeout": float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
        "max_retries": int(os.getenv("LLM_MAX_RETRIES", "2")),
    }
    if provider in {"gemini", "google"}:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("已选择 Gemini，但缺少 GEMINI_API_KEY")
        # Gemini provides an OpenAI-compatible endpoint, so no extra package is required.
        return ChatOpenAI(
            model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
            api_key=api_key,
            base_url=os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"),
            **common,
        )
    if provider in {"claude", "anthropic"}:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("已选择 Claude，但缺少 ANTHROPIC_API_KEY")
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise RuntimeError("缺少 langchain-anthropic，请重新安装 requirements.txt") from exc
        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            api_key=api_key,
            **common,
        )
    if provider not in {"deepseek", "openai_compatible"}:
        raise RuntimeError("LLM_PROVIDER 只能是 deepseek、claude、gemini 或 openai_compatible")
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY，请检查 .env 配置")
    return ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        **common,
    )


def clean_email_text(text: str, max_chars: int = MAX_EMAIL_CHARS) -> str:
    """Remove token-heavy HTML, tracking URLs and quoted reply history."""
    text = unescape(text or "")
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"https?://\S{200,}", "[长链接已省略]", text)
    # Common reply separators. The newest message before the separator is enough.
    text = re.split(
        r"(?im)^\s*(?:-{2,}\s*(?:original message|原始邮件)\s*-{2,}|"
        r"on .{0,160} wrote:|在 .{0,160} 写道：)\s*$",
        text,
        maxsplit=1,
    )[0]
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith(">")]
    return "\n".join(lines)[:max_chars]


def fetch_email_node(state: dict[str, Any]) -> dict[str, Any]:
    try:
        emails = get_email_client().fetch_unread_emails(limit=state.get("email_limit", 5))
        if not emails:
            return {"emails": [], "email_content": "", "fetch_error": None}
        first = emails[0]
        return {
            "emails": emails,
            "email_content": f"发件人: {first['from']}\n主题: {first['subject']}\n正文: {first['body']}",
            "current_email_id": first["id"],
            "fetch_error": None,
        }
    except Exception as exc:
        return {"emails": [], "email_content": "", "fetch_error": str(exc)}


def _parse_json(content: Any) -> dict[str, Any]:
    if not isinstance(content, str):
        content = str(content)
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        raise ValueError("模型未返回有效 JSON")
    return json.loads(match.group(0))


def analyze_email_node(state: dict[str, Any]) -> dict[str, Any]:
    """Produce summary, urgency and reply in one call instead of three."""
    raw_email_text = state.get("email_content", "") or ""
    is_ad_subject = bool(re.search(
        r"(?im)^\s*主题\s*:\s*[<＜]\s*广告\s*[>＞]", raw_email_text
    ))
    lowered_email = raw_email_text.lower()
    is_enterprise_notice = any(name in lowered_email for name in ENTERPRISE_SENDERS)
    needs_account_action = any(word in lowered_email for word in ACCOUNT_ACTION_WORDS)
    email_text = clean_email_text(raw_email_text)
    if not email_text:
        return {"summary": "（无邮件内容可总结）", "urgency": "未知", "draft_reply": ""}

    instruction = (state.get("user_instruction") or "处理").strip()[:500]
    system = SystemMessage(content=(
        "你是邮件助理。分析邮件并仅返回一个JSON对象，不要Markdown。字段必须为："
        '"summary"（不超过80字）、"urgency"（只能是紧急/普通/低）、'
        '"draft_reply"（简洁、礼貌，不虚构承诺或答案）。'
        "紧急仅指明确截止、事故、故障、安全或立即行动；广告通知通常为低，其余为普通。"
        "回复使用来信语言；若指令要求不回复，draft_reply返回空字符串。"
    ))
    response = get_llm().invoke([
        system,
        HumanMessage(content=f"用户指令：{instruction}\n\n邮件：\n{email_text}"),
    ])
    data = _parse_json(response.content)
    urgency = str(data.get("urgency", "普通")).strip()
    # An explicit advertisement subject always has low priority, even if its
    # promotional copy contains words such as “立即”.
    if is_ad_subject:
        urgency = "低"
    elif is_enterprise_notice and not needs_account_action:
        urgency = "低"
    return {
        "summary": str(data.get("summary", "")).strip(),
        "urgency": urgency if urgency in VALID_URGENCIES else "普通",
        "draft_reply": str(data.get("draft_reply", "")).strip(),
    }
