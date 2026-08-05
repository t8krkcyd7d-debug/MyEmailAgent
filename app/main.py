"""
main.py - FastAPI Web 服务入口

启动后，客户端可以通过 HTTP 请求调用我们的智能邮件处理功能。

类比 C++：类似于用 libmicrohttpd 启动一个 RESTful 服务。
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.models import (
    EmailProcessRequest,
    EmailProcessResponse,
    FetchEmailsResponse,
    EmailItem,
    SendEmailRequest,
    EmailActionRequest,
    AnalyzeMessageRequest,
    PriorityRequest,
    TodoRequest,
    PriorityRuleRequest,
)
from app.email_client import get_email_accounts, get_email_client
from app.store import apply_rule, create_rule, create_todo, delete_rule, delete_todo, list_rules, list_todos, priorities_for, set_priority, update_todo
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# 必须在加载 .env 后导入图；模型客户端由节点按需创建。
from app.graph import analysis_graph, inbox_graph

# ---------- 1. 创建 FastAPI 应用 ----------
app = FastAPI(
    title="邮件智能处理系统",
    description="基于 LangGraph的智能邮件处理服务，支持摘要、紧急程度分类和自动回复草稿生成。",
    version="2.0.0",
)
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ---------- 2. 健康检查 ----------
@app.get("/health")
async def health_check():
    """
    最简单的健康检查接口，用于确认服务是否运行。
    """
    return {"status": "ok", "message": "服务运行正常"}


# ---------- 3. 处理用户提供的邮件文本 ----------
@app.post("/process_email", response_model=EmailProcessResponse)
async def process_email(request: EmailProcessRequest):
    """
    接收客户端发来的邮件内容，运行 LangGraph 工作流，
    返回摘要、紧急程度和回复草稿。

    请求体 JSON 示例：
    {
        "email_content": "紧急：服务器宕机，请立即处理！",
        "user_instruction": "处理"
    }

    返回示例：
    {
        "summary": "邮件报告服务器宕机，需立即处理。",
        "urgency": "紧急",
        "draft_reply": "已收到通知，我们正在处理，预计10分钟内恢复。",
        "error": null
    }
    """
    try:
        # 调用 LangGraph 工作流，传入初始状态
        # 注意：我们只需要提供 email_content，其他字段由节点填充
        final_state = analysis_graph.invoke({
            "email_content": request.email_content,
            "user_instruction": request.user_instruction,
        })

        # 提取结果
        summary = final_state.get("summary", "")
        urgency = final_state.get("urgency", "")
        draft = final_state.get("draft_reply", "")

        return EmailProcessResponse(
            summary=summary,
            urgency=urgency,
            draft_reply=draft,
            error=None
        )

    except Exception as e:
        # 发生任何异常，返回 HTTP 500 错误
        raise HTTPException(status_code=500, detail=str(e))


# ---------- 4. 获取并处理真实未读邮件 ----------
@app.get("/fetch_and_process", response_model=FetchEmailsResponse)
async def fetch_and_process(limit: int = Query(default=5, ge=1, le=50)):
    """
    从 IMAP 服务器获取未读邮件，并对第一封邮件运行智能处理。

    参数：
        limit: 最多获取的邮件数量（默认 5）

    返回：
        邮件列表及第一封邮件的处理结果
    """
    try:
        # 调用工作流，初始状态中 email_content 为空，
        # 但 fetch_email_node 会从 IMAP 读取并填充。
        initial_state = {
            "email_content": "",   # 空，由节点填充
            "email_limit": limit,
        }
        final_state = inbox_graph.invoke(initial_state)

        # 检查是否有错误
        if final_state.get("fetch_error"):
            return FetchEmailsResponse(
                status="error",
                total=0,
                processed=None,
                emails=[],
                message=final_state["fetch_error"]
            )

        emails = final_state.get("emails", [])
        if not emails:
            return FetchEmailsResponse(
                status="ok",
                total=0,
                processed=None,
                emails=[],
                message="收件箱中没有未读邮件"
            )

        # 构造处理结果
        processed_info = {
            "summary": final_state.get("summary", ""),
            "urgency": final_state.get("urgency", ""),
            "draft_reply": final_state.get("draft_reply", ""),
        }

        # 转换邮件列表为响应模型
        email_items = []
        for e in emails:
            email_items.append(EmailItem(
                id=e['id'],
                from_addr=e['from'],
                subject=e['subject'],
                date=e['date'],
                is_read=False  # 因为我们读取时标记为未读，实际未改动
            ))

        return FetchEmailsResponse(
            status="ok",
            total=len(email_items),
            processed=processed_info,
            emails=email_items,
            message="处理成功"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- 5. 根路径 ----------
@app.get("/api/mailbox")
async def mailbox(folder: str = "INBOX", limit: int = Query(50, ge=1, le=100), q: str = "", account: str = "all"):
    try:
        clients = get_email_accounts()
        selected = clients.items() if account == "all" else [(account, get_email_client(account))]
        emails = []
        for account_id, client in selected:
            items = client.list_emails(folder=folder, limit=limit, query=q)
            for item in items:
                item["account"] = account_id
                item["account_label"] = client.label
                item["account_address"] = client.email_address
            emails.extend(items)
        from email.utils import parsedate_to_datetime
        def timestamp(item):
            try: return parsedate_to_datetime(item.get("date", "")).timestamp()
            except Exception: return 0
        emails = sorted(emails, key=timestamp, reverse=True)[:limit]
        rules = list_rules()
        for email in emails:
            overrides = priorities_for(f'{email["account"]}:{folder}')
            if email["id"] in overrides:
                email["urgency"] = overrides[email["id"]]
                email["priority_is_manual"] = True
            else:
                matched = apply_rule(rules, email.get("from", ""), email.get("subject", ""))
                if matched:
                    email["urgency"] = matched
                    email["priority_rule_applied"] = True
        return {"status": "ok", "folder": folder, "emails": emails, "total": len(emails)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/mailbox/{email_id}")
async def email_detail(email_id: int, folder: str = "INBOX", account: str | None = None):
    try:
        item = get_email_client(account).get_email(email_id, folder)
        if not item:
            raise HTTPException(status_code=404, detail="没有找到这封邮件")
        return item
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/mailbox/{email_id}/action")
async def email_action(email_id: int, request: EmailActionRequest):
    try:
        get_email_client(request.account).update_email(email_id, request.action, request.folder)
        return {"status": "ok", "message": "操作成功"}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/mailbox/{email_id}/analyze", response_model=EmailProcessResponse)
async def analyze_message(email_id: int, request: AnalyzeMessageRequest):
    try:
        item = get_email_client(request.account).get_email(email_id, request.folder)
        if not item:
            raise HTTPException(status_code=404, detail="没有找到这封邮件")
        final_state = analysis_graph.invoke({
            "email_content": f"发件人: {item['from']}\n主题: {item['subject']}\n正文: {item['body']}",
            "user_instruction": request.instruction,
        })
        return EmailProcessResponse(summary=final_state.get("summary", ""), urgency=final_state.get("urgency", ""), draft_reply=final_state.get("draft_reply", ""))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/send")
async def send_message(request: SendEmailRequest):
    if "@" not in request.to:
        raise HTTPException(status_code=422, detail="请填写有效的收件人邮箱")
    if not get_email_client(request.account).send_email(request.to, request.subject or "（无主题）", request.body):
        raise HTTPException(status_code=502, detail="发送失败，请检查邮箱设置后重试")
    return {"status": "ok", "message": "邮件已发送"}


@app.put("/api/mailbox/{email_id}/priority")
async def change_priority(email_id: int, request: PriorityRequest):
    set_priority(f"{request.account or 'default'}:{request.folder}", email_id, request.urgency)
    return {"status": "ok", "urgency": request.urgency}


@app.get("/api/todos")
async def todos():
    return {"status": "ok", "todos": list_todos()}


@app.post("/api/todos")
async def add_todo(request: TodoRequest):
    todo_id = create_todo(request.email_id, request.folder, request.title, request.due_at)
    return {"status": "ok", "id": todo_id}


@app.patch("/api/todos/{todo_id}")
async def complete_todo(todo_id: int, completed: bool = True):
    update_todo(todo_id, completed)
    return {"status": "ok"}


@app.delete("/api/todos/{todo_id}")
async def remove_todo(todo_id: int):
    delete_todo(todo_id)
    return {"status": "ok"}


@app.get("/api/priority-rules")
async def priority_rules():
    return {"status": "ok", "rules": list_rules()}


@app.post("/api/priority-rules")
async def add_priority_rule(request: PriorityRuleRequest):
    if not request.sender_contains.strip() and not request.subject_contains.strip():
        raise HTTPException(status_code=422, detail="请至少填写一个发件人或主题关键词")
    rule_id = create_rule(request.name, request.sender_contains.strip(), request.subject_contains.strip(), request.urgency)
    return {"status": "ok", "id": rule_id}


@app.delete("/api/priority-rules/{rule_id}")
async def remove_priority_rule(rule_id: int):
    delete_rule(rule_id)
    return {"status": "ok"}


@app.get("/api/account")
async def account_info():
    accounts = [{"id": key, "label": client.label, "address": client.email_address}
                for key, client in get_email_accounts().items()]
    return {"configured": bool(accounts), "address": accounts[0]["address"] if accounts else "", "accounts": accounts}


@app.get("/")
async def root():
    """
    根路径，返回可用接口列表。
    """
    return FileResponse(STATIC_DIR / "index.html")


# ---------- 启动脚本（直接运行此文件时启动） ----------
if __name__ == "__main__":
    import uvicorn
    # 启动服务，监听所有网卡，端口 8000
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
