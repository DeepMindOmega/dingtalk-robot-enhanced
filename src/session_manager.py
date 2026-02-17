#!/usr/bin/env python3
"""
OpenCode 会话管理器
为每个对话维护独立的会话 ID，实现对话记忆功能
"""

import json
import uuid
from pathlib import Path
from datetime import datetime


class SessionManager:
    def __init__(self, sessions_file: str):
        self.sessions_file = Path(sessions_file)
        self.sessions_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_file()

    def _init_file(self):
        if not self.sessions_file.exists():
            self._write({})

    def _read(self) -> dict:
        try:
            with open(self.sessions_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def _write(self, data: dict):
        with open(self.sessions_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_session_key(
        self, user_id: str, conv_id: str = "", conv_type: str = "1"
    ) -> str:
        """
        生成会话键
        - 私聊 (conv_type="1"): user_id
        - 群聊 (conv_type="2"): conv_id (群聊共享会话)
        """
        if conv_type == "2" and conv_id:
            return f"group:{conv_id}"
        return f"user:{user_id}"

    def should_continue_session(
        self, user_id: str, conv_id: str = "", conv_type: str = "1"
    ) -> bool:
        """
        检查是否应该继续已有会话
        返回 True 如果存在有效会话，否则 False
        """
        key = self.get_session_key(user_id, conv_id, conv_type)
        sessions = self._read()
        return key in sessions and "session_id" in sessions[key]

    def get_session_id(
        self, user_id: str, conv_id: str = "", conv_type: str = "1"
    ) -> str:
        """
        获取现有会话 ID，不存在则返回空字符串
        返回格式: ses_{uuid}
        """
        key = self.get_session_key(user_id, conv_id, conv_type)
        sessions = self._read()

        if key in sessions:
            return sessions[key].get("session_id", "")

        return ""

    def create_new_session(
        self, user_id: str, conv_id: str = "", conv_type: str = "1"
    ) -> str:
        """
        强制创建新会话（用于"新对话"命令）
        """
        key = self.get_session_key(user_id, conv_id, conv_type)
        sessions = self._read()

        new_session_id = f"ses_{uuid.uuid4().hex[:12]}"
        sessions[key] = {
            "session_id": new_session_id,
            "created_at": datetime.now().isoformat(),
            "last_used": datetime.now().isoformat(),
        }
        self._write(sessions)
        return new_session_id

    def delete_session(self, user_id: str, conv_id: str = "", conv_type: str = "1"):
        """
        删除指定会话
        """
        key = self.get_session_key(user_id, conv_id, conv_type)
        sessions = self._read()

        if key in sessions:
            del sessions[key]
            self._write(sessions)
            return True
        return False

    def update_last_used(self, user_id: str, conv_id: str = "", conv_type: str = "1"):
        """
        更新会话最后使用时间
        """
        key = self.get_session_key(user_id, conv_id, conv_type)
        sessions = self._read()

        if key in sessions:
            sessions[key]["last_used"] = datetime.now().isoformat()
            self._write(sessions)

    def update_session_id(
        self, user_id: str, conv_id: str, conv_type: str, session_id: str
    ):
        """
        更新会话 ID
        """
        key = self.get_session_key(user_id, conv_id, conv_type)
        sessions = self._read()

        if key in sessions:
            sessions[key]["session_id"] = session_id
            sessions[key]["last_used"] = datetime.now().isoformat()
            self._write(sessions)
        else:
            sessions[key] = {
                "session_id": session_id,
                "created_at": datetime.now().isoformat(),
                "last_used": datetime.now().isoformat(),
            }
            self._write(sessions)

    def get_all_sessions(self) -> dict:
        """
        获取所有会话信息
        """
        return self._read()

    def cleanup_old_sessions(self, days: int = 7):
        """
        清理超过指定天数的未使用会话
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)
        sessions = self._read()

        to_delete = []
        for key, data in sessions.items():
            try:
                last_used = datetime.fromisoformat(data.get("last_used", ""))
                if last_used < cutoff:
                    to_delete.append(key)
            except:
                pass

        for key in to_delete:
            del sessions[key]

        if to_delete:
            self._write(sessions)
            return len(to_delete)
        return 0


if __name__ == "__main__":
    sm = SessionManager("/tmp/sessions.json")

    user_id = "test_user"
    conv_id = "test_group"
    conv_type = "2"

    print(f"Get session: {sm.get_session_id(user_id, conv_id, conv_type)}")
    print(f"Same session: {sm.get_session_id(user_id, conv_id, conv_type)}")

    new_session = sm.create_new_session(user_id, conv_id, conv_type)
    print(f"New session: {new_session}")

    print(f"Cleanup: {sm.cleanup_old_sessions()} old sessions")
