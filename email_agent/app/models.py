"""
models.py - 定义 API 的请求和响应数据结构

"""

# 从 pydantic 导入基类
from pydantic import BaseModel, Field
from typing import Literal, Optional


# ---------- 1. 客户端请求模型 ----------
class EmailProcessRequest(BaseModel):
    """
    用户调用 /process_email 时 POST 的 JSON 体格式。

    类比 C++ 结构体：
    struct EmailProcessRequest {
        std::string email_content;
        std::string user_instruction;
    };

    Pydantic 会自动校验字段是否存在、类型是否正确。
    """
    email_content: str = Field(min_length=1, max_length=100_000)
    user_instruction: str = Field(default="处理", max_length=500)


# ---------- 2. 服务器响应模型 ----------
class EmailProcessResponse(BaseModel):
    """
    返回给客户端的 JSON 响应格式。

    类比 C++ 结构体：
    struct EmailProcessResponse {
        std::string summary;
        std::string urgency;
        std::string draft_reply;
        std::optional<std::string> error;  // C++17 的 optional
    };
    """
    summary: str                # 邮件摘要
    urgency: str                # 紧急程度（"紧急"/"普通"/"低"）
    draft_reply: str            # 生成的回复草稿
    error: Optional[str] = None # 错误信息（可选，默认 None）


# ---------- 3. 获取邮件列表的响应 ----------
class EmailItem(BaseModel):
    """单封邮件的摘要信息（用于列表展示）"""
    id: int
    from_addr: str     
    subject: str
    date: str
    is_read: bool = False


class FetchEmailsResponse(BaseModel):
    """GET /fetch_and_process 的响应"""
    status: str          # "ok" 或 "error"
    total: int           # 获取到的邮件总数
    processed: Optional[dict] = None  # 智能处理结果（摘要+紧急度+回复）
    emails: list[EmailItem] = Field(default_factory=list)
    message: Optional[str] = None    # 额外信息


class SendEmailRequest(BaseModel):
    account: Optional[str] = None
    to: str = Field(min_length=3, max_length=500)
    subject: str = Field(default="", max_length=500)
    body: str = Field(min_length=1, max_length=100_000)


class EmailActionRequest(BaseModel):
    action: Literal["read", "unread", "star", "unstar", "trash", "delete"]
    folder: str = Field(default="INBOX", max_length=200)
    account: Optional[str] = None


class AnalyzeMessageRequest(BaseModel):
    folder: str = Field(default="INBOX", max_length=200)
    instruction: str = Field(default="请总结并起草回复", max_length=500)
    account: Optional[str] = None


class PriorityRequest(BaseModel):
    folder: str = Field(default="INBOX", max_length=200)
    urgency: Literal["紧急", "普通", "低"]
    account: Optional[str] = None


class TodoRequest(BaseModel):
    email_id: int
    folder: str = Field(default="INBOX", max_length=200)
    title: str = Field(min_length=1, max_length=500)
    due_at: Optional[str] = Field(default=None, max_length=50)


class PriorityRuleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sender_contains: str = Field(default="", max_length=200)
    subject_contains: str = Field(default="", max_length=200)
    urgency: Literal["紧急", "普通", "低"]
