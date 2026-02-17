#!/usr/bin/env python3
"""
Memory System Client
智能记忆系统客户端，提供钉钉机器人与记忆系统的完整集成
"""

import requests
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

MEMORY_API_BASE = "http://localhost:8000"
logger = logging.getLogger(__name__)


class MemorySystemClient:
    """记忆系统客户端"""

    def __init__(self, api_base: str = MEMORY_API_BASE):
        self.api_base = api_base
        self.session = requests.Session()

    def health_check(self) -> bool:
        try:
            response = self.session.get(f"{self.api_base}/health", timeout=3)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Memory system health check failed: {e}")
            return False

    def search_memories(
        self, keyword: str, limit: int = 5, hybrid: bool = True
    ) -> List[Dict[str, Any]]:
        """
        搜索记忆

        Args:
            keyword: 搜索关键词
            limit: 返回结果数量
            hybrid: 是否使用混合搜索

        Returns:
            匹配的记忆列表
        """
        try:
            response = self.session.post(
                f"{self.api_base}/query/search",
                json={"keyword": keyword, "limit": limit, "hybrid": hybrid},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])
            return []
        except Exception as e:
            logger.error(f"Search memories failed: {e}")
            return []

    def create_memory(
        self,
        title: str,
        content: str,
        category: str = "context",
        tags: Optional[List[str]] = None,
        memory_type: str = "long_term",
    ) -> Optional[Dict[str, Any]]:
        """
        创建记忆

        Args:
            title: 记忆标题
            content: 记忆内容
            category: 分类
            tags: 标签列表
            memory_type: 记忆类型

        Returns:
            创建的记忆对象，失败返回None
        """
        try:
            data = {
                "title": title,
                "content": content,
                "type": memory_type,
                "category": category,
                "tags": tags or [],
            }

            response = self.session.post(
                f"{self.api_base}/memories/", json=data, timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Memory created: {result.get('id')}")
                return result
            else:
                logger.error(f"Create memory failed: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Create memory failed: {e}")
            return None

    def create_experience_memory(
        self,
        title: str,
        problem: str,
        solution: str,
        category: str = "success_case",
        tags: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        创建经验记忆（结构化）

        Args:
            title: 经验标题
            problem: 问题描述
            solution: 解决方案
            category: 分类
            tags: 标签

        Returns:
            创建的记忆对象
        """
        content = f"""## 问题描述
{problem}

## 解决方案
{solution}

## 记录时间
{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

        return self.create_memory(
            title=title, content=content, category=category, tags=tags
        )

    def get_recent_memories(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的记忆"""
        try:
            response = self.session.get(
                f"{self.api_base}/query/recent", params={"limit": limit}, timeout=5
            )
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            logger.error(f"Get recent memories failed: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        try:
            response = self.session.get(f"{self.api_base}/query/statistics", timeout=5)
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            logger.error(f"Get statistics failed: {e}")
            return {}


_memory_client: Optional[MemorySystemClient] = None


def get_memory_client() -> MemorySystemClient:
    global _memory_client
    if _memory_client is None:
        _memory_client = MemorySystemClient()
    return _memory_client


def format_memories_as_context(
    memories: List[Dict[str, Any]], max_chars: int = 3000
) -> str:
    """
    将搜索结果格式化为OpenCode上下文

    Args:
        memories: 记忆列表
        max_chars: 最大字符数

    Returns:
        格式化的上下文字符串
    """
    if not memories:
        return ""

    context_parts = ["# 相关经验记忆\n"]

    for mem in memories:
        title = mem.get("title", "No title")
        content = mem.get("content", "")

        content_preview = content[:500] + "..." if len(content) > 500 else content

        context_parts.append(f"## {title}")
        context_parts.append(content_preview)
        context_parts.append("")

        total_chars = len("\n".join(context_parts))
        if total_chars >= max_chars:
            context_parts.append(f"\n...(共{len(memories)}条记忆，已截断)")
            break

    return "\n".join(context_parts)


def should_use_memory_system(message: str) -> bool:
    """
    智能判断是否需要使用记忆系统

    Args:
        message: 用户消息

    Returns:
        是否应该检索记忆
    """
    complex_patterns = [
        "如何",
        "怎么",
        "怎么做",
        "how to",
        "how do",
        "解决",
        "问题",
        "错误",
        "error",
        "problem",
        "经验",
        "建议",
        "优化",
        "improve",
        "optimize",
        "配置",
        "设置",
        "config",
        "setting",
        "部署",
        "安装",
        "deploy",
        "install",
        "调试",
        "debug",
    ]

    simple_patterns = [
        "你好",
        "hello",
        "hi",
        "谢谢",
        "thank",
        "再见",
        "bye",
        "1+1",
        "1+1=",
        "计算",
        "calculate",
        "天气",
        "weather",
    ]

    message_lower = message.lower()

    for pattern in simple_patterns:
        if pattern in message_lower:
            return False

    for pattern in complex_patterns:
        if pattern in message_lower:
            return True

    return len(message) >= 20


def extract_experience_from_conversation(
    messages: List[Dict[str, Any]], user_id: str, conv_id: str
) -> List[Dict[str, str]]:
    """
    从对话历史中提取经验

    Args:
        messages: 消息列表
        user_id: 用户ID
        conv_id: 对话ID

    Returns:
        提取的经验列表
    """
    experiences = []

    # 提取成功案例
    for i, msg in enumerate(messages):
        content = msg.get("content", "")
        role = msg.get("role", "")

        # 检查成功模式
        if role == "assistant" and ("成功" in content or "完成" in content):
            # 提取上下文
            context_messages = messages[max(0, i - 2) : i + 1]
            context_text = "\n".join([m.get("content", "") for m in context_messages])

            experiences.append(
                {
                    "type": "success_case",
                    "title": f"成功解决: {content[:50]}",
                    "content": context_text,
                    "tags": ["success", user_id, conv_id],
                }
            )

        # 检查错误模式
        if role == "assistant" and ("错误" in content or "失败" in content):
            # 提取错误和解决方案
            context_messages = messages[max(0, i - 3) : i + 1]
            context_text = "\n".join([m.get("content", "") for m in context_messages])

            experiences.append(
                {
                    "type": "failure_lesson",
                    "title": f"错误教训: {content[:50]}",
                    "content": context_text,
                    "tags": ["failure", user_id, conv_id],
                }
            )

    return experiences
