# 钉钉机器人 - 快速开始指南

## ✅ 状态：已启动并运行

钉钉机器人已经在后台成功启动并连接到钉钉服务器！

## 📱 如何使用

### 1. 在钉钉中找到机器人
打开钉钉应用，搜索你的机器人（使用配置的 App 名称）

### 2. 发送消息测试
直接给机器人发送任意消息，例如：
- `列出文件` - 查看当前目录
- `状态` - 查看系统状态
- `帮助` - 查看所有命令

### 3. 支持的命令

| 命令 | 功能 | 示例 |
|------|------|------|
| 列出文件 | 显示当前目录文件列表 | `列出文件` |
| 查看 <文件> | 读取文件内容 | `查看 test.py` |
| 执行 <命令> | 运行 shell 命令 | `执行 ls -la` |
| 状态 | 显示系统状态 | `状态` |
| 帮助 | 显示帮助信息 | `帮助` |
| 天气 [城市] | 查询天气 | `天气 北京` |

### 4. Markdown 支持
机器人会自动识别 Markdown 格式：
- 代码块：使用 \`\`\`
- 标题：使用 ## 或 ###
- 列表：使用 - 或 *
- 粗体：使用 **text**

## 🛠️ 服务管理

### 启动服务
```bash
cd ~/.opencode/skills/dingtalk-robot
./start.sh
```

### 停止服务
```bash
cd ~/.opencode/skills/dingtalk-robot
./stop.sh
```

### 查看日志
```bash
# 实时查看网关日志
tail -f logs/gateway.log

# 实时查看处理器日志
tail -f logs/processor.log

# 查看最近 50 行
tail -50 logs/gateway.log
```

### 检查服务状态
```bash
ps aux | grep -E "gateway.py|processor.py" | grep -v grep
```

## 📊 当前状态

- ✅ Gateway 进程: 运行中
- ✅ Processor 进程: 运行中
- ✅ Token: 已缓存（有效期至 12:07:58）
- ✅ 连接: 已连接到钉钉 WebSocket
- ✅ 心跳监控: 运行中

## 🔧 配置信息

配置文件位置: `~/.opencode/skills/dingtalk-robot/config.json`

当前配置：
- CLIENT_ID: your_dingtalk_app_key_here
- AUTHORIZED_USERS: 2 个用户
- QUEUE_DIR: /home/admin/.opencode/skills/dingtalk-robot/queue

## ❓ 故障排除

### 机器人没有回复？
1. 检查服务是否运行：`ps aux | grep gateway.py`
2. 查看日志：`tail -f logs/gateway.log`
3. 检查网络连接：确保能访问 api.dingtalk.com

### 收到"未授权"提示？
需要将你的用户 ID 添加到 config.json 的 AUTHORIZED_USERS 列表中。

### Token 过期？
系统会自动刷新 Token，无需手动干预。如果失败，查看日志中的错误信息。

### 想重启服务？
```bash
cd ~/.opencode/skills/dingtalk-robot
./stop.sh
./start.sh
```

## 📚 更多功能

- **Token 自动刷新**: 过期前 5 分钟自动刷新，无需重启
- **错误重试**: 失败的消息会自动重试 3 次
- **Markdown 渲染**: 自动识别并显示格式化内容
- **详细日志**: 完整的操作日志，方便调试

## 🆕 飞书机器人

如果你也想使用飞书机器人，需要先配置：

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建自建应用
3. 获取 APP_ID 和 APP_SECRET
4. 编辑 `~/.opencode/skills/feishu-robot/config.json`
5. 配置 Webhook URL（需要公网 IP）

详细说明请查看 `~/.opencode/skills/PLATFORM_COMPARISON.md`

---

**现在就可以在钉钉中使用机器人了！** 🎉
