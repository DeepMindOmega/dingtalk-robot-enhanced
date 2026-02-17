# 钉钉机器人控制插件 (增强版)

通过钉钉私聊或群聊@机器人来控制 OpenCode。

## 功能
- 接收钉钉消息（私聊/群聊@机器人）
- 任务队列处理
- 多代理协作执行任务
- 执行 shell 命令
- 文件操作
- 智能对话
- **Token 自动缓存和刷新**
- **Markdown 富文本消息支持**
- **图片/文件上传**
- **增强的错误处理和重试机制**

## 配置
在 `config.json` 中设置钉钉应用凭证：
```json
{
  "CLIENT_ID": "your_app_key",
  "CLIENT_SECRET": "your_app_secret",
  "AUTHORIZED_USERS": ["user_id_1", "user_id_2"],
  "QUEUE_DIR": "/path/to/queue"
}
```

## 使用
```bash
# 启动完整服务
python3 start.py

# 或分别启动
python3 src/gateway.py    # 消息网关
python3 src/processor.py  # 任务处理器
```

## 钉钉命令
- 直接发消息 - 智能对话（超时: 60秒，智能体: quick）
- `列出文件` - 列出目录
- `查看 <文件>` - 读取文件
- `执行 <命令>` - 运行命令
- `状态` - 系统状态
- `帮助` - 显示帮助

**配置**:
- OpenCode 超时: 60 秒
- 指定智能体: quick（最快响应速度）

**说明**: 使用 `quick` 智能体，针对简单任务优化，提供最快的响应速度。

## 工作截图功能
每次发送消息后，自动发送相关工作截图。

### 工作原理
- OpenCode 执行任务时生成截图（如网页截图、操作截图等）
- Processor 自动检测 `/home/admin/.local/share/opencode` 目录中新生成的图片文件
- Gateway 自动上传并发送相关工作截图到钉钉
- 日志标记: `[工作截图]`

### 支持的截图类型
- 网页截图（Playwright 等工具）
- 操作截图（自动化工具生成）
- 任何保存在 OpenCode 工作目录的图片文件

### 注意事项
- 只发送 OpenCode 执行任务时生成的新图片
- 如果没有生成工作截图，只发送文字消息
- 不再发送默认图片

## 图片发送 API
### 发送图片到群聊
```python
from src.gateway import upload_media, send_group_message, get_access_token

token = get_access_token()
media_id = upload_media('/path/to/image.png', token)
result = send_group_message(conv_id, "", token, "image", None, media_id)
```

### 发送图片到私聊
```python
from src.gateway import upload_media, send_private_message, get_access_token

token = get_access_token()
media_id = upload_media('/path/to/image.png', token)
result = send_private_message(user_id, "", token, "image", None, media_id)
```

### API 说明
- `upload_media(file_path, token)` - 上传图片，返回 media_id
- `send_group_message(conv_id, content, token, msg_type, title, image_key)` - 发送群聊消息
- `send_private_message(user_id, content, token, msg_type, title, image_key)` - 发送私聊消息

## 新增功能
- **自动 Markdown 检测**: 消息中包含 Markdown 格式时自动使用富文本显示
- **Token 缓存**: 自动管理 Access Token，减少 API 调用
- **错误重试**: 失败的请求会自动重试（最多3次）
- **媒体上传**: 支持上传图片和文件到钉钉
- **工作截图自动发送**: 每次消息自动发送相关工作截图
- **详细日志**: 更完善的日志记录，方便调试
