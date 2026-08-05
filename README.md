# MyMails 智能邮件管理系统

MyMails 是一套简单易用的网页邮件管理系统，用户可以在浏览器中收取、阅读、搜索和发送邮件，并使用智能助手生成邮件摘要与回复建议。

## 主要功能

- 查看收件箱、已发送和回收站
- 按发件人或主题搜索邮件
- 筛选未读邮件和星标邮件
- 标记已读、未读或星标
- 移入回收站及永久删除邮件
- 手动修改邮件紧急程度
- 为邮件创建提醒或待办事项
- 写邮件、回复和转发邮件
- 自动生成邮件摘要和建议回复
- 自动判断邮件紧急程度
- 支持电脑和手机浏览器
- 支持多个授权码邮箱，并在“全部邮箱”中统一查看

紧急程度的显示方式：

| 分类 | 显示 | 判断原则 |
| --- | --- | --- |
| 紧急 | `!!!` | 有明确截止时间、事故、故障、安全风险或需要立即行动 |
| 普通 | `!!` | 日常工作、沟通和一般通知 |
| 低 | `!` | 广告、推广、订阅等非必要信息 |

## 使用说明

## 部署说明

### 运行环境

- Windows 10/11、macOS 或 Linux
- Python 3.10 及以上版本
- 支持 IMAP/SMTP 的邮箱账号
- DeepSeek API Key
- 或 Gemini / Claude API Key

### 1. 安装项目

进入项目目录并创建 Python 虚拟环境：

```bash
cd email_agent
python3 -m venv venv
```

macOS 或 Linux：

```bash
source venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell：

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 配置系统

复制配置模板：

macOS 或 Linux：

```bash
cp .env.example .env
```

Windows：

```powershell
copy .env.example .env
```

打开 `.env`，填写以下配置：

```dotenv
DEEPSEEK_API_KEY=sk-你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

EMAIL_IMAP_SERVER=imap.example.com
EMAIL_IMAP_PORT=993
EMAIL_SMTP_SERVER=smtp.example.com
EMAIL_SMTP_PORT=465
EMAIL_ADDRESS=your_email@example.com
EMAIL_PASSWORD=邮箱授权码

EMAIL_TRASH_FOLDER=Trash
```

请使用邮箱服务商生成的“授权码”或“应用专用密码”，不要填写邮箱登录密码。

常见邮箱服务器：

| 邮箱 | IMAP | SMTP |
| --- | --- | --- |
| QQ 邮箱 | `imap.qq.com:993` | `smtp.qq.com:465` |
| 163 邮箱 | `imap.163.com:993` | `smtp.163.com:465` |
| Gmail | `imap.gmail.com:993` | `smtp.gmail.com:465` |
| Outlook | `outlook.office365.com:993` | `smtp.office365.com:587` |

不同邮箱的已发送和回收站名称可能不同。如果相应页面无法打开，请根据邮箱服务商实际名称修改邮件夹配置。

### 3. 配置多个邮箱（可选）

如果需要聚合多个邮箱，请在 `.env` 中增加单行配置。设置后，系统会使用这里的账号代替单邮箱配置：

```dotenv
EMAIL_ACCOUNTS_JSON=[{"id":"work","label":"工作邮箱","address":"work@qq.com","password":"邮箱授权码","imap_server":"imap.qq.com","imap_port":993,"smtp_server":"smtp.qq.com","smtp_port":465,"trash_folder":"Trash"},{"id":"personal","label":"个人邮箱","address":"me@163.com","password":"邮箱授权码","imap_server":"imap.163.com","imap_port":993,"smtp_server":"smtp.163.com","smtp_port":465,"trash_folder":"Trash"}]
```

每个 `id` 必须唯一。修改配置后需要重启系统。网页顶部可以选择“全部邮箱”或单个账号，写信时也可以选择发件邮箱。

当前多账号方式使用邮箱授权码或应用专用密码。Gmail、Outlook 等账号如果禁止授权码登录，需要后续配置 OAuth 登录支持。

### 4. 启动系统

macOS 或 Linux：

```bash
./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Windows：

```powershell
.\venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000
```

本机访问地址为 `http://localhost:8000`。同一局域网内的其他设备需要使用运行电脑的 IP 地址，例如 `http://192.168.1.10:8000`。

`0.0.0.0` 仅为服务器监听地址，不应直接在浏览器中打开。

### 5. 停止系统

回到运行服务的命令行窗口，按 `Ctrl + C`。

### 怎么用

启动系统后，在浏览器中打开：

```text
http://localhost:8000
```

### 阅读和处理邮件

1. 点击左侧“收件箱”。
2. 点击邮件列表中的任意邮件查看正文。
3. 使用邮件顶部按钮进行星标、标记未读或删除。
4. 点击“总结并起草回复”，可获得智能摘要和建议回复。
5. 点击“使用建议回复”，确认内容无误后发送。

### 写邮件

1. 点击左上角“写邮件”。
2. 填写收件人、主题和正文。
3. 检查邮箱地址与正文内容。
4. 点击“发送邮件”。

### 搜索邮件

在顶部搜索框中输入发件人或主题，然后按回车键。清空搜索框并按回车，可重新显示全部邮件。

### 删除邮件

普通删除会将邮件移入回收站。在回收站中选择“永久删除”后，邮件无法恢复，请谨慎操作。


## 安全说明

- `.env` 包含邮箱授权码和 API Key，必须妥善保管。
- 不要通过聊天软件、邮件或截图公开 `.env` 内容。
- 建议为系统单独创建邮箱授权码，并定期更换。
- 建议仅部署在可信电脑、企业内网或配置 HTTPS 的服务器上。
- 发送 AI 分析请求时，待分析的邮件正文会提交至配置的模型服务。涉及敏感数据时，请先确认客户的数据合规要求。
- 系统不会在用户仅查看邮件时自动修改正文或删除邮件。

## 常见问题

### 页面打不开或显示空白

确认服务正在运行，并访问 `http://localhost:8000`，不要访问 `http://0.0.0.0:8000`。仍有问题时，使用 `Ctrl + Shift + R` 强制刷新页面。

### 邮箱登录失败

确认邮箱已开启 IMAP/SMTP 服务，并使用授权码而非登录密码。部分邮箱在修改授权设置后需要等待几分钟才能生效。

### 无法打开回收站

邮箱服务商使用的回收站名称可能不是 `Trash`。请登录邮箱网页版确认名称，并修改 `.env` 中的 `EMAIL_TRASH_FOLDER`。

### 邮件发送失败

检查 SMTP 地址、端口和授权码。端口 465 使用 SSL，端口 587 使用 STARTTLS。

### 智能摘要不可用

检查 `DEEPSEEK_API_KEY` 是否正确、账户余额是否充足，以及运行电脑能否访问模型服务。

### 没有显示新邮件

点击页面顶部的刷新按钮。确认邮件确实已到达当前配置的邮箱账号。

## 测试

可执行自动测试：

```bash
./venv/bin/python -m unittest discover -s tests -v
```

健康检查地址：

```text
http://localhost:8000/health
```

返回以下内容表示服务正常：

```json
{"status":"ok","message":"服务运行正常"}
```

## 项目结构

```text
email_agent/
├── app/
│   ├── main.py            # Web 服务与接口
│   ├── email_client.py    # 邮件收发和管理
│   ├── nodes.py           # 智能分析逻辑
│   ├── graph.py           # 智能处理流程
│   ├── models.py          # 数据格式
│   └── static/            # MyMails 网页界面
├── tests/                 # 自动测试
├── .env.example           # 配置模板
├── requirements.txt       # Python 依赖
└── README.md              # 本文档
```
