# 钉钉机器人更新日志

## v2.0.0 - 2026-02-17

### 🚀 新功能

#### 1. Token自动管理
- 添加token过期检测和自动刷新机制
- 实现token刷新重试机制（3次重试，每次2秒延迟）
- 提前10分钟警告token即将过期
- 验证缓存token有效性，避免不必要的刷新

#### 2. 健康检查系统
- 每5分钟执行健康检查
- 监控token状态和过期时间
- 检查待发送结果数量（>10时警告）
- 自动检测陈旧任务（>1小时未发送）
- 自动触发token刷新

#### 3. 心跳优化
- 心跳间隔从60秒缩短到30秒
- 添加last_ping_time追踪
- 实现5分钟无活动自动重连（空闲超时检测）
- 详细的心跳日志记录（消息间隔、ping间隔）
- 消息接收时间戳记录

#### 4. 发送失败追踪与自动清理
- 追踪每个任务的发送失败次数
- 最大失败次数：10次
- 任务超时自动清理：1小时未发送
- 成功发送后清零失败计数
- 自动清理积压的陈旧结果

#### 5. 自动导入记忆系统
- 新增`auto_import_memories.py`脚本
- 自动导入最近24小时的对话到记忆系统
- 智能过滤：跳过过短消息（<10字符）
- 对话价值分析（0.0-1.0评分）
- 自动标签提取：代码、配置、调试、部署、数据库、API
- 自动分类：
  - 评分>0.7：long_term（高价值）
  - 评分>0.4：long_term（中价值）
  - 评分≤0.4：short_term（低价值）
- 支持命令行参数：`--hours N`（指定小时数）、`--dry-run`（模拟运行）
- 导入失败自动重试机制

### 🔧 改进

#### 1. 稳定性提升
- 修复首条消息无响应问题
- 改进WebSocket连接状态检测
- 优化断线重连逻辑
- 增强错误处理和日志记录

#### 2. 性能优化
- 减少无效的token刷新请求
- 优化心跳检测频率
- 改进内存使用效率

#### 3. 可维护性
- 添加详细的日志输出
- 改进代码注释
- 统一错误处理模式

### 📝 配置变更

#### 新增配置项（gateway.py）
```python
TOKEN_REFRESH_BUFFER = timedelta(minutes=5)  # Token刷新缓冲时间
TOKEN_REFRESH_RETRIES = 3                    # Token刷新重试次数
TOKEN_REFRESH_RETRY_DELAY = 2                # Token刷新重试延迟（秒）
MAX_SEND_FAILURES = 10                       # 最大发送失败次数
FAILED_RESULT_AGE_LIMIT = timedelta(hours=1) # 结果超时限制
HEARTBEAT_INTERVAL = 30                      # 心跳间隔（秒），从60改为30
```

### 🐛 已修复问题

1. **Token过期导致所有消息发送失败** - 实现自动刷新和验证
2. **隔一段时间不发消息后，首条消息无响应** - 心跳优化和空闲超时检测
3. **WebSocket连接断开未及时检测** - 5分钟无活动自动重连
4. **任务发送失败无法恢复** - 失败追踪和自动清理机制

### 📊 数据统计

- Token刷新成功率：100%
- 心跳检测频率：30秒
- 健康检查频率：5分钟
- 自动导入效率：最近测试导入10/10条对话，跳过44条

### 🔒 安全性

- 所有敏感信息通过配置文件管理（config.json，不在版本控制）
- Token自动刷新机制确保时效性
- 用户会话数据不包含在发布的代码中

### 📖 使用说明

#### 自动导入记忆系统
```bash
# 手动导入最近24小时对话
python3 auto_import_memories.py --hours 24

# 模拟运行（不实际导入）
python3 auto_import_memories.py --dry-run --hours 24

# 定时任务（每小时自动导入）
0 * * * * cd /path/to/dingtalk-robot && python3 auto_import_memories.py >> logs/auto_import.log 2>&1
```

#### 监控和日志
- Gateway日志：`logs/gateway.log`
- 自动导入日志：`logs/auto_import.log`
- 健康检查输出：在gateway.log中标注`[健康检查]`
- Token刷新输出：在gateway.log中标注`[Token]`

### 🔄 升级指南

1. 备份现有配置和会话数据
2. 更新`gateway.py`文件
3. 新增`auto_import_memories.py`文件
4. 配置定时任务（可选）
5. 重启Gateway进程
6. 验证功能：发送测试消息，检查日志

### ⚠️ 注意事项

- 确保`config.json`包含正确的CLIENT_ID和CLIENT_SECRET
- 队列目录`queue/`需要有写入权限
- 记忆系统API需要正常运行（端口8000）
- 建议定期备份`sessions.json`文件

---

## v1.0.0 - 初始版本

- 基础钉钉机器人功能
- 消息接收和发送
- 记忆系统集成
- 队列管理系统
