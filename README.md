# 钉钉机器人 OpenCode 集成插件

## 📋 简介

这是一个将钉钉机器人与 OpenCode AI 助手集成的插件。通过此插件，您可以在钉钉群聊中直接与 OpenCode 交互，让 OpenCode 帮助您完成各种任务。

## 🚀 快速开始

### 1. 解压插件

```bash
tar -xzf dingtalk-robot-plugin.tar.gz
cd dingtalk-robot
```

### 2. 配置机器人

**重要：插件使用 config.local.json 来存储实际配置（不会被提交到Git）**

#### 创建本地配置文件

```bash
cp config.example.json config.local.json
vi config.local.json
```

编辑 `config.local.json`：

```json
{
  "CLIENT_ID": "你的钉钉AppKey",
  "CLIENT_SECRET": "你的钉钉AppSecret",
  "AUTHORIZED_USERS": [
    "用户ID1",
    "用户ID2"
  ],
  "QUEUE_DIR": "/path/to/your/queue/directory"
}
```

### 3. 获取钉钉凭证

1. 访问 https://open-dev.dingtalk.com/
2. 创建应用或使用现有应用
3. 获取 ClientID 和 ClientSecret
4. 添加到 config.local.json

### 4. 启动服务

```bash
./start.sh
```

### 5. 使用机器人

在钉钉群聊中@机器人，发送任何消息即可。

## 📱 使用方法

### 基本使用

1. 在钉钉群聊中添加机器人
2. @机器人发送消息
3. 机器人会立即回复"收到，处理中..."
4. 几秒钟内返回 OpenCode 的智能回复

### 可用指令

机器人支持以下快捷指令：

- **列出文件** - 查看当前目录
- **查看 <文件名>** - 读取文件内容
- **执行 <命令>** - 运行系统命令
- **状态** - 查看系统状态
- **帮助** - 显示帮助信息

**注意：您也可以直接发送任何问题或请求，OpenCode 会智能处理。**

## 📊 服务管理

### 查看状态

```bash
./status.sh
```

### 查看日志

```bash
# Gateway 日志
tail -f logs/gateway.log

# Processor 日志
tail -f logs/processor.log
```

### 停止服务

```bash
./stop.sh
```

### 重启服务

```bash
./stop.sh && ./start.sh
```

## 🔧 配置说明

### 配置文件说明

插件会按以下优先级查找配置文件：

1. `config.local.json` - 本地配置（包含真实密钥，不会被提交）
2. `config.json` - 默认配置

### 配置项说明

| 配置项 | 说明 | 示例 |
|--------|------|------|
| CLIENT_ID | 钉钉应用的 AppKey | your_dingtalk_app_key_here |
| CLIENT_SECRET | 钉钉应用的 AppSecret | your_secret_here |
| AUTHORIZED_USERS | 允许使用机器人的用户ID列表 | ["$:LWCP_v1:user_id"] |
| QUEUE_DIR | 队列目录路径 | /path/to/queue |

## 🛡️ 安全说明

### 敏感信息保护

- `config.local.json` 包含真实配置，已添加到 `.gitignore`
- 不会将敏感信息提交到 Git 仓库
- 配置示例使用占位符，不包含真实密钥

### 建议的安全实践

1. 不要将 `config.local.json` 提交到版本控制
2. 定期更换 AppSecret
3. 限制 AUTHORIZED_USERS，只添加信任的用户
4. 定期检查日志文件，不要提交到版本控制

## 📚 文档

- [快速开始指南](./QUICKSTART.md)
- [技能说明](./SKILL.md)

## ⚠️ 注意事项

1. **钉钉开放平台配置**
   - 确保机器人状态为"已发布"
   - 配置正确的权限（接收群消息、发送消息）
   - 确认机器人类型为"企业内部机器人"

2. **OpenCode 要求**
   - 确保已安装 OpenCode CLI
   - 默认路径：`/home/admin/.npm-global/bin/opencode`
   - 如需修改，编辑 `src/processor.py` 中的 `OPENCODE_BIN`

3. **系统要求**
   - Python 3.7+
   - Linux 环境
   - 网络连接（访问钉钉 API 和 OpenCode）

## 🐛 故障排查

### 机器人无响应

1. 检查服务状态：`./status.sh`
2. 查看日志：`tail -f logs/gateway.log`
3. 确认机器人是否在群聊中
4. 确认是否@机器人（群聊中必须@）

### 连接错误

1. 检查网络连接
2. 验证 CLIENT_ID 和 CLIENT_SECRET 是否正确
3. 查看 Gateway 日志中的错误信息

### OpenCode 调用失败

1. 检查 OpenCode 是否正确安装
2. 查看 Processor 日志
3. 确认 OpenCode 路径是否正确

## 📝 更新日志

### v1.0 (2026-02-14)
- ✅ 完整的 OpenCode 集成
- ✅ 支持群聊和单聊
- ✅ 自动消息类型检测
- ✅ Markdown、ActionCard 消息支持
- ✅ Token 自动刷新和缓存
- ✅ 重试机制和错误处理
- ✅ 媒体上传支持
- ✅ 心跳监控和自动重连
- ✅ 配置安全处理（config.local.json）

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题，请通过以下方式联系：
- 提交 GitHub Issue
- 查看 [QUICKSTART.md](./QUICKSTART.md)

---

**祝使用愉快！** 🎉
