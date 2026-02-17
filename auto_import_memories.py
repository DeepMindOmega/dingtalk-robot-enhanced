#!/usr/bin/env python3
import json
import requests
import logging
import time
from datetime import datetime, timedelta

DINGTALK_ROBOT_DIR = "/home/admin/.opencode/skills/dingtalk-robot"
MEMORY_API_BASE = "http://localhost:8000"
IMPORT_HOURS = 24
MIN_MESSAGE_LENGTH = 10

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_tasks():
    tasks_file = f"{DINGTALK_ROBOT_DIR}/queue/tasks.json"
    with open(tasks_file, "r") as f:
        return json.load(f)


def get_recent_tasks(hours=IMPORT_HOURS):
    tasks = load_tasks()
    now = datetime.now()
    cutoff_time = now - timedelta(hours=hours)
    recent_tasks = []
    for tid, task in tasks.items():
        status = task.get("status")
        completed_at = task.get("completed_at")
        if status != "completed" or not completed_at:
            continue
        try:
            dt = datetime.fromisoformat(completed_at)
            if dt >= cutoff_time:
                recent_tasks.append(task)
        except Exception as e:
            logger.debug(f"解析时间失败: {e}")
    return recent_tasks


def extract_conversations(tasks):
    conversations = []
    skipped = 0
    for task in tasks:
        message = task.get("message", "").strip()
        result = task.get("result", "").strip()
        user_nick = task.get("user_nick", "用户")
        created_at = task.get("created_at", "")

        if not result or len(result) < 10:
            skipped += 1
            continue

        if len(message) < 10:
            skipped += 1
            continue

        conversation = {
            "title": f"对话记录 - {user_nick}",
            "content": f"用户: {message}\n\n助手: {result}",
            "source": "dingtalk_bot",
            "created_at": created_at,
            "task_id": task.get("id"),
            "user_nick": user_nick,
        }

        conversations.append(conversation)

    return conversations, skipped


def analyze_conversation_value(conversation):
    content = conversation.get("content", "")
    value_score = 0.5

    tech_keywords = ["如何", "解决", "错误", "问题", "bug", "代码", "配置"]
    if any(kw in content.lower() for kw in tech_keywords):
        value_score += 0.2

    if 100 < len(content) < 2000:
        value_score += 0.1

    if "解决" in content or "成功" in content:
        value_score += 0.1

    if "错误" in content or "失败" in content or "问题" in content:
        value_score += 0.1

    return min(value_score, 1.0)


def convert_to_memory_format(conversation):
    value_score = analyze_conversation_value(conversation)

    if value_score > 0.7:
        memory_type = "long_term"
    elif value_score > 0.4:
        memory_type = "long_term"
    else:
        memory_type = "short_term"

    tags = []
    content_lower = conversation.get("content", "").lower()

    tag_keywords = {
        "代码": ["代码", "编程", "函数", "class", "def"],
        "配置": ["配置", "设置", "config"],
        "调试": ["调试", "debug", "错误"],
        "部署": ["部署", "部署", "发布"],
        "数据库": ["数据库", "database", "sql"],
        "API": ["api", "接口", "请求"],
    }

    for tag, keywords in tag_keywords.items():
        if any(kw in content_lower for kw in keywords):
            tags.append(tag)

    return {
        "type": memory_type,
        "title": conversation.get("title"),
        "content": conversation.get("content"),
        "tags": tags[:5],
        "source": conversation.get("source"),
        "created_at": conversation.get("created_at"),
        "score": value_score,
    }


def import_conversation(memory_data):
    url = f"{MEMORY_API_BASE}/api/v1/memories/"

    try:
        response = requests.post(url, json=memory_data, timeout=10)
        if response.status_code in [200, 201]:
            logger.info(f"导入成功: {memory_data['title'][:50]}")
            return True
        else:
            logger.error(f"导入失败: {response.status_code} - {response.text[:100]}")
            return False
    except requests.exceptions.Timeout:
        logger.error(f"请求超时: {memory_data['title'][:50]}")
        return False
    except Exception as e:
        logger.error(f"导入异常: {memory_data['title'][:50]} - {e}")
        return False


def run_import(hours=IMPORT_HOURS, dry_run=False):
    logger.info("=" * 60)
    logger.info("开始自动导入对话到记忆系统")
    logger.info(f"导入范围: 最近{hours}小时")
    logger.info(f"最小消息长度: {MIN_MESSAGE_LENGTH}字符")
    logger.info("=" * 60)

    try:
        response = requests.get(f"{MEMORY_API_BASE}/health", timeout=5)
        if response.status_code != 200:
            logger.error("记忆系统不可用")
            return
    except Exception as e:
        logger.error(f"无法连接记忆系统: {e}")
        return

    logger.info("正在加载最近的任务...")
    recent_tasks = get_recent_tasks(hours)
    logger.info(f"找到 {len(recent_tasks)} 个最近完成的任务")

    if not recent_tasks:
        logger.info("没有需要导入的任务")
        return

    logger.info("正在分析对话...")
    conversations, skipped = extract_conversations(recent_tasks)
    logger.info(f"提取了 {len(conversations)} 条对话，跳过 {skipped} 条")

    if not conversations:
        logger.info("没有符合导入条件的对话")
        return

    if dry_run:
        logger.info("【模拟模式】不会实际导入")
        for conv in conversations[:10]:
            memory_data = convert_to_memory_format(conv)
            print(f"\n  标题: {memory_data['title']}")
            print(f"  类型: {memory_data['type']}")
            print(f"  得分: {memory_data['score']:.2f}")
            print(f"  标签: {memory_data['tags']}")
            print(f"  内容: {memory_data['content'][:80]}...")
    else:
        logger.info("开始导入对话...")
        success_count = 0
        for conv in conversations:
            memory_data = convert_to_memory_format(conv)
            if import_conversation(memory_data):
                success_count += 1
            time.sleep(0.1)

        logger.info("=" * 60)
        logger.info("导入完成")
        logger.info(f"成功导入: {success_count}/{len(conversations)}")
        logger.info(f"跳过: {skipped} 条")
        logger.info("=" * 60)


if __name__ == "__main__":
    import sys

    hours = IMPORT_HOURS
    dry_run = False

    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--dry-run":
            dry_run = True
        elif arg == "--hours":
            if i + 1 < len(sys.argv[1:]):
                hours = int(sys.argv[1:][i + 1])

    run_import(hours=hours, dry_run=dry_run)
