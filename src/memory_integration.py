#!/usr/bin/env python3
"""
智能记忆集成模块
集成记忆系统到钉钉机器人，实现智能检索和自动学习
"""

import os
import logging
from typing import Optional, List, Dict, Any
from memory_client import (
    MemorySystemClient,
    get_memory_client,
    should_use_memory_system,
    format_memories_as_context,
    extract_experience_from_conversation,
)

logger = logging.getLogger(__name__)


class MemoryIntegration:
    """记忆系统集成器"""

    def __init__(self):
        self.memory_client = get_memory_client()
        self.enabled = True

    def check_system_status(self) -> Dict[str, Any]:
        """检查记忆系统状态"""
        return {
            "enabled": self.enabled,
            "available": self.memory_client.health_check(),
            "statistics": self.memory_client.get_statistics(),
        }

    def enhance_with_memory(
        self, user_message: str, user_id: str, conv_id: str
    ) -> Optional[str]:
        """
        增强用户消息，添加相关记忆上下文

        Args:
            user_message: 用户原始消息
            user_id: 用户ID
            conv_id: 对话ID

        Returns:
            增强后的消息（包含记忆上下文），无需增强则返回None
        """
        if not self.enabled:
            return None

        if not should_use_memory_system(user_message):
            return None

        logger.info(f"Searching memory for: {user_message[:50]}...")

        memories = self.memory_client.search_memories(
            keyword=user_message, limit=5, hybrid=True
        )

        if not memories:
            logger.info("No relevant memories found")
            return None

        memory_context = format_memories_as_context(memories, max_chars=3000)

        logger.info(f"Found {len(memories)} relevant memories")

        enhanced_message = f"""{user_message}

---

# 相关经验记忆（来自记忆系统）
{memory_context}

---

请根据上述相关经验记忆，结合你的知识，提供准确的答案。如果记忆中的信息不完整或过时，请明确说明。"""

        return enhanced_message

    def save_conversation_as_experience(
        self, messages: List[Dict[str, Any]], user_id: str, conv_id: str, conv_type: str
    ) -> int:
        """
        自动从对话历史中提取经验并保存

        Args:
            messages: 对话消息列表
            user_id: 用户ID
            conv_id: 对话ID
            conv_type: 对话类型（1=私聊, 2=群聊）

        Returns:
            保存的经验数量
        """
        if not self.enabled:
            return 0

        if len(messages) < 2:
            return 0

        logger.info(f"Extracting experiences from conversation: {conv_id}")

        experiences = extract_experience_from_conversation(messages, user_id, conv_id)
        saved_count = 0

        for exp in experiences:
            try:
                result = self.memory_client.create_memory(
                    title=exp["title"],
                    content=exp["content"],
                    category=exp["type"],
                    tags=exp["tags"],
                )

                if result:
                    saved_count += 1
                    logger.info(f"Saved experience: {result.get('id')}")

            except Exception as e:
                logger.error(f"Failed to save experience: {e}")

        logger.info(f"Saved {saved_count}/{len(experiences)} experiences")
        return saved_count

    def get_memory_statistics(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        if not self.enabled:
            return {"enabled": False}

        stats = self.memory_client.get_statistics()
        stats["enabled"] = True
        return stats

    def manual_query_memory(
        self, keyword: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        手动查询记忆（通过命令触发）

        Args:
            keyword: 搜索关键词
            limit: 返回数量

        Returns:
            搜索结果列表
        """
        if not self.enabled:
            return []

        logger.info(f"Manual memory query: {keyword}")
        return self.memory_client.search_memories(
            keyword=keyword, limit=limit, hybrid=True
        )


_memory_integration: Optional[MemoryIntegration] = None


def get_memory_integration() -> MemoryIntegration:
    global _memory_integration
    if _memory_integration is None:
        _memory_integration = MemoryIntegration()
    return _memory_integration


MEMORY_COMMANDS = {
    "记忆查询": lambda integration, args: integration.manual_query_memory(
        args[0] if args else ""
    ),
    "记忆统计": lambda integration, args: integration.get_memory_statistics(),
    "记忆状态": lambda integration, args: integration.check_system_status(),
    "memory query": lambda integration, args: integration.manual_query_memory(
        args[0] if args else ""
    ),
    "memory stats": lambda integration, args: integration.get_memory_statistics(),
    "memory status": lambda integration, args: integration.check_system_status(),
}


def handle_memory_command(command: str, args: List[str]) -> Optional[str]:
    """
    处理记忆系统相关命令

    Args:
        command: 命令名称
        args: 命令参数

    Returns:
        命令响应文本
    """
    integration = get_memory_integration()

    if command not in MEMORY_COMMANDS:
        return None

    try:
        result = MEMORY_COMMANDS[command](integration, args)

        if command in ["记忆查询", "memory query"]:
            memories = result
            if not memories:
                return "未找到相关记忆"

            response = f"找到 {len(memories)} 条相关记忆：\n\n"
            for i, mem in enumerate(memories[:5], 1):
                title = mem.get("title", "No title")[:50]
                response += f"{i}. {title}\n"
            return response

        elif command in ["记忆统计", "memory stats"]:
            stats = result
            total = stats.get("total", 0)
            by_type = stats.get("by_type", {})

            return f"""记忆系统统计：
- 总记忆数: {total}
- 长期记忆: {by_type.get("long_term", 0)}
- 成功案例: {by_type.get("success_case", 0)}
- 短期记忆: {by_type.get("short_term", 0)}
- 上下文: {by_type.get("context", 0)}"""

        elif command in ["记忆状态", "memory status"]:
            return (
                f"记忆系统状态: {'✅ 正常' if result.get('available') else '❌ 不可用'}"
            )

    except Exception as e:
        logger.error(f"Handle memory command failed: {e}")
        return f"记忆系统命令执行失败: {e}"

    return None
