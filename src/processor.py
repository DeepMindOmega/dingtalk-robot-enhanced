#!/usr/bin/env python3
import json
import subprocess
import os
import sys
import time
from datetime import datetime
import logging
from pathlib import Path

sys.path.insert(0, "/home/admin/.opencode/skills/dingtalk-robot/src")
logger = logging.getLogger(__name__)
from queue_manager import QueueManager
from session_manager import SessionManager
from memory_integration import get_memory_integration, handle_memory_command


# Token 管理器 - 跟踪会话 token 使用量
class TokenTracker:
    def __init__(self):
        self.session_tokens = {}  # session_id -> total_tokens

    def get_total(self, session_id):
        return self.session_tokens.get(session_id, 0)

    def add(self, session_id, tokens):
        self.session_tokens[session_id] = self.get_total(session_id) + tokens

    def should_compact(self, session_id, threshold=100000):
        return self.get_total(session_id) >= threshold

    def compact(self, session_id):
        if session_id in self.session_tokens:
            # compact 后减半（假设压缩后只保留 50%）
            self.session_tokens[session_id] = self.session_tokens[session_id] // 2

    def reset(self, session_id):
        self.session_tokens[session_id] = 0


# 全局 token 跟踪器
token_tracker = TokenTracker()


def parse_tokens_from_output(output):
    """从 OpenCode JSON 输出中提取 token 使用量"""
    try:
        lines = output.strip().split("\n")
        for line in lines:
            data = json.loads(line)
            if data.get("type") == "step_finish" and "tokens" in data:
                tokens = data["tokens"]
                total = tokens.get("total", 0)
                return total
        return 0
    except:
        return 0


def run_opencode_compact(session_id):
    """执行 opencode compact 命令压缩会话"""
    try:
        cmd = [
            OPENCODE_BIN,
            "run",
            "/compact",
            "--session",
            session_id,
            "--format",
            "json",
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, cwd="/home/admin"
        )
        if result.returncode == 0:
            logger.info(f"会话 {session_id} compact 成功")
        else:
            logger.error(f"会话 {session_id} compact 失败: {result.stderr}")
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Compact 异常: {e}")
        return False


CONFIG_DIR = "/home/admin/.opencode/skills/dingtalk-robot"
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.local.json")
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
with open(CONFIG_PATH, "r") as f:
    CONFIG = json.load(f)

qm = QueueManager(CONFIG["QUEUE_DIR"])
sm = SessionManager(os.path.join(CONFIG_DIR, "sessions.json"))
OPENCODE_BIN = "/home/admin/.npm-global/bin/opencode"

print(f"配置文件: {CONFIG_PATH}")
print(f"OpenCode路径: {OPENCODE_BIN}")


def run_opencode(
    message, continue_session=False, images=None, timeout=60, session_id=None
):
    opencode_dir = "/home/admin/.local/share/opencode"
    screenshots_before = set()

    if os.path.exists(opencode_dir):
        for root, dirs, files in os.walk(opencode_dir):
            for file in files:
                if file.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                    screenshots_before.add(os.path.join(root, file))

    try:
        cmd = [OPENCODE_BIN, "run", "--agent", "quick", message, "--format", "json"]
        if session_id:
            cmd.extend(["--session", session_id])
        if images:
            for img_path in images:
                if os.path.exists(img_path):
                    cmd.extend(["--file", img_path])
                    print(f"    → 附加文件: {img_path}")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd="/home/admin"
        )
        output = result.stdout if result.stdout else ""
        error = result.stderr if result.stderr else ""

        screenshots_after = set()
        if os.path.exists(opencode_dir):
            for root, dirs, files in os.walk(opencode_dir):
                for file in files:
                    if file.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                        screenshots_after.add(os.path.join(root, file))

        generated_images = list(screenshots_after - screenshots_before)

        if not output and not generated_images:
            return "OpenCode 执行完成（无输出）", None, generated_images, 0

        lines = output.strip().split("\n")
        response_text = []
        extracted_session_id = None
        tokens_used = 0

        print(f"  🔍 OpenCode 输出行数: {len(lines)}")

        for line in lines:
            try:
                data = json.loads(line)
                msg_type = data.get("type")
                print(f"  🔍 处理行类型: {msg_type}")

                if msg_type == "text":
                    response_text.append(data.get("part", {}).get("text", ""))
                if "sessionID" in data:
                    extracted_session_id = data["sessionID"]
                if msg_type == "step_finish":
                    tokens = data.get("part", {}).get("tokens", {})
                    tokens_used = tokens.get("total", 0)
                    print(f"  🔍 解析到 tokens: {tokens}")
            except Exception as e:
                print(f"  🔍 解析异常: {e}")
                pass

        response = "\n".join(response_text) if response_text else "无输出"
        return response, extracted_session_id, generated_images, tokens
    except subprocess.TimeoutExpired:
        return "命令超时 (" + str(timeout) + "s)", None, [], 0
    except FileNotFoundError:
        return "错误: 找不到 OpenCode: " + OPENCODE_BIN, None, [], 0
    except Exception as e:
        return "执行异常: " + str(e), None, [], 0


def execute_shell(cmd, timeout=30, cwd="/home/admin"):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=cwd
        )
        output = result.stdout + result.stderr
        return output[:2000] if output else "(无输出)"
    except subprocess.TimeoutExpired:
        return "命令超时 (" + str(timeout) + "s)"
    except Exception as e:
        return "执行错误: " + str(e)


def process_task(task):
    msg = task.get("message", "").strip()
    user_id = task.get("user_id", "")
    user_nick = task.get("user_nick", "用户")
    conv_id = task.get("conv_id", "")
    conv_type = task.get("conv_type", "1")
    images = task.get("images", [])
    msg_lower = msg.lower()
    parts = msg.split()
    first_word = parts[0] if parts else ""

    if msg in ["新对话", "new", "reset"]:
        new_session = sm.create_new_session(user_id, conv_id, conv_type)
        return "✅ 已创建新对话，之前的上下文已清除", []

    if first_word in ["私聊", "发私信", "发私聊", "dm"] and len(parts) > 1:
        target_user = parts[1].strip("@")
        target_msg = " ".join(parts[2:]) if len(parts) > 2 else "你好"

        if target_user:
            return f"[私聊:{target_user}] {target_msg}", []
        else:
            return "❌ 请指定要发送私聊的用户，例如：私聊 @用户ID 你好", []

    if first_word in ["查看", "读取", "cat"] and len(parts) > 1:
        filename = parts[-1].strip("'\"")
        filepath = "/home/admin/" + filename
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read(2000)
            return "📄 " + filename + ":\n\n" + content, []
        return "❌ 文件不存在: " + filename, []

    if first_word in ["执行", "运行"] and len(parts) > 1:
        cmd = " ".join(parts[1:])
        return "🔧 " + cmd + "\n```\n" + execute_shell(cmd) + "\n```", []

    if msg in ["状态", "status", "/status"]:
        return "📊 系统状态\n⏰ " + str(datetime.now()) + "\n📂 /home/admin", []

    if msg in ["帮助", "help", "/help"]:
        return (
            """🤖 OpenCode 助手

 📝 可用指令:
 • 直接发送任意指令 - OpenCode 会执行并回复（带上下文记忆）
 • 新对话 - 清除上下文，开启新对话
 • 查看 <文件> - 读取文件
 • 执行 <命令> - 运行命令
 • 状态 - 系统信息
 • 帮助 - 显示帮助

 💬 每个对话会自动记忆上下文！
 📷 支持发送和接收图片！""",
            [],
        )

    current_session_id = sm.get_session_id(user_id, conv_id, conv_type)

    should_compact = token_tracker.should_compact(current_session_id)

    if should_compact:
        print("  ⚠️  会话 Token 超过 100000，执行 compact 压缩上下文...")
        compact_success = run_opencode_compact(current_session_id)
        if compact_success:
            token_tracker.compact(current_session_id)
            print("  ✅ 会话已压缩")
        else:
            print("  ❌ Compact 失败，继续执行...")

    continue_session = sm.should_continue_session(user_id, conv_id, conv_type)

    opencode_msg = msg

    memory_integration = get_memory_integration()
    memory_context = memory_integration.enhance_with_memory(msg, user_id, conv_id)
    if memory_context:
        opencode_msg = memory_context
        print("  🧠 已注入记忆上下文")

    image_sending_guide = """

---

【重要提示】如果需要发送图片到钉钉（群聊或私聊），请使用以下方法：

**方法 1: 使用钉钉机器人内置 API**（推荐）
```python
from src.gateway import upload_media, send_group_message, send_private_message, get_access_token

token = get_access_token()
media_id = upload_media('/path/to/image.png', token)

send_group_message(conv_id, "", token, "image", None, media_id)

send_private_message(user_id, "", token, "image", None, media_id)
```

**方法 2: 生成图片后返回 media_id**
如果你的任务会生成图片文件，请返回媒体文件路径，系统会自动上传并发送。

**API 参数说明:**
- `upload_media(file_path, token)` - 上传图片，返回格式如 `@lALPD1nnwUYxhMHNASzNAZA` 的 media_id
- `send_group_message(conv_id, content, token, "image", None, media_id)` - 群聊发送图片
- `send_private_message(user_id, content, token, "image", None, media_id)` - 私聊发送图片

**当前环境信息:**
- 当前是群聊时，conversation_id: `"{}"`
- 当前是私聊时，user_id: `"{}"`
""".format(conv_id, user_id)

    valid_images = None
    if images:
        print(f"  → 附加 {len(images)} 张图片")
        valid_images = [img for img in images if os.path.exists(img)]
        if valid_images:
            opencode_msg = msg
            for img_path in valid_images:
                opencode_msg += f"\n[已附加图片: {img_path}]"
        else:
            opencode_msg = msg + "\n[无法读取图片文件]"

    opencode_msg += image_sending_guide

    print("  → 转发给 OpenCode: " + opencode_msg[:50] + "...")
    print("  → 继续会话: " + ("是" if continue_session else "否"))
    response, new_session_id, generated_images, tokens = run_opencode(
        opencode_msg,
        session_id=current_session_id if current_session_id else None,
        images=valid_images if valid_images else None,
    )

    tokens_total = tokens.get("total", 0) if isinstance(tokens, dict) else 0
    tokens_input = tokens.get("input", 0) if isinstance(tokens, dict) else 0
    tokens_output = tokens.get("output", 0) if isinstance(tokens, dict) else 0
    tokens_reasoning = tokens.get("reasoning", 0) if isinstance(tokens, dict) else 0
    cache_read = (
        tokens.get("cache", {}).get("read", 0) if isinstance(tokens, dict) else 0
    )
    cache_write = (
        tokens.get("cache", {}).get("write", 0) if isinstance(tokens, dict) else 0
    )

    if tokens_total > 0:
        token_tracker.add(current_session_id, tokens_total)

    total_tokens = token_tracker.get_total(current_session_id)
    print(f"  📊 Token 使用: 本次 {tokens_total}, 累计 {total_tokens}")
    print(f"  📝 响应原始长度: {len(response)}")

    token_info = f"""

---
📊 **Token 使用**
• **总使用**: {tokens_total:,}
• **输入**: {tokens_input:,}
• **输出**: {tokens_output:,}
• **推理**: {tokens_reasoning:,}
• **缓存读取**: {cache_read:,}
• **会话累计**: {total_tokens:,}"""
    response += token_info
    print(f"  📝 响应添加 token 后长度: {len(response)}")

    if (
        new_session_id
        and new_session_id.startswith("ses_")
        and new_session_id != current_session_id
    ):
        print("  → 新会话 ID: " + new_session_id)
        sm.update_session_id(user_id, conv_id, conv_type, new_session_id)
        # 重置新会话的 token 计数
        token_tracker.reset(new_session_id)

    has_screenshot = "截图" in response or "screenshot" in response.lower()
    has_image_response = "图片" in response or "image" in response.lower()

    if generated_images:
        print(f"  → 生成相关工作截图: {len(generated_images)} 张")
        for img in generated_images:
            print(f"      - {img}")

    if len(response) > 5000:
        response = response[:5000] + "\n\n...(输出过长，已截断)"

    memory_integration = get_memory_integration()
    saved_count = memory_integration.save_conversation_as_experience(
        [{"role": "user", "content": msg}], user_id, conv_id, conv_type
    )
    if saved_count > 0:
        print(f"  📝 自动保存 {saved_count} 条经验到记忆系统")

    return response, generated_images


def main():
    print("[" + str(datetime.now()) + "] 钉钉任务处理器启动 (OpenCode 集成版)")
    print("队列目录: " + CONFIG["QUEUE_DIR"])
    print("OpenCode 路径: " + OPENCODE_BIN)
    processed = set()

    while True:
        try:
            tasks = qm.get_pending_tasks()
            for tid, task in tasks.items():
                if tid in processed:
                    continue

                print("\n[" + datetime.now().strftime("%H:%M:%S") + "] 处理: " + tid)
                print("  用户: " + task.get("user_nick"))
                print("  消息: " + task.get("message"))

                response, images = process_task(task)
                print("  回复长度: " + str(len(response)) + " 字符")

                qm.complete_task(tid, response)
                qm.add_result(
                    tid,
                    task["user_id"],
                    response,
                    task.get("conv_id", ""),
                    task.get("conv_type", "1"),
                    images,
                )

                memory_integration = get_memory_integration()
                memory_integration.save_conversation_as_experience(
                    [{"role": "assistant", "content": response}],
                    task["user_id"],
                    task.get("conv_id", ""),
                    task.get("conv_type", "1"),
                )
                processed.add(tid)
                print("  ✓ 完成")
        except Exception as e:
            print("错误: " + str(e))
            import traceback

            traceback.print_exc()

        time.sleep(2)


if __name__ == "__main__":
    main()
