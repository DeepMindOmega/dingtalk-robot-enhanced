#!/usr/bin/env python3
"""
Enhanced DingTalk Gateway with:
- Token caching
- Rich message support (markdown, cards)
- Improved error handling and retry logic
- Media upload support
"""

import logging
import json
import urllib.request
import time
import threading
import sys
import os
import asyncio
import hashlib
import base64
import random
import glob
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from queue_manager import QueueManager

MEDIA_DIR = os.path.join(os.path.dirname(__file__), "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

CONFIG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.local.json")
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

with open(CONFIG_PATH, "r") as f:
    CONFIG = json.load(f)

CLIENT_ID = CONFIG["CLIENT_ID"]
CLIENT_SECRET = CONFIG["CLIENT_SECRET"]
AUTHORIZED_USERS = CONFIG["AUTHORIZED_USERS"]
QUEUE_DIR = CONFIG["QUEUE_DIR"]

MAX_MESSAGE_LENGTH = 1500

DEFAULT_IMAGES_DIR = "/home/admin/.opencode/skills/dingtalk-robot/default_images"


def get_random_default_image():
    images = glob.glob(os.path.join(DEFAULT_IMAGES_DIR, "*.png"))
    images.extend(glob.glob(os.path.join(DEFAULT_IMAGES_DIR, "*.jpg")))
    images.extend(glob.glob(os.path.join(DEFAULT_IMAGES_DIR, "*.jpeg")))
    if images:
        return random.choice(images)
    return None


def split_long_message(content: str, msg_type: str = "text") -> list[str]:
    if len(content) <= MAX_MESSAGE_LENGTH:
        return [content]

    messages = []
    if msg_type == "markdown":
        parts = []
        current_part = ""
        lines = content.split("\n")
        in_code_block = False

        for line in lines:
            if line.strip().startswith("```"):
                if in_code_block:
                    current_part += line + "\n"
                    in_code_block = False
                    parts.append(current_part)
                    current_part = ""
                else:
                    if current_part:
                        parts.append(current_part)
                        current_part = ""
                    current_part = line + "\n"
                    in_code_block = True
                continue

            if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                if current_part:
                    parts.append(current_part)
                current_part = line + "\n"
            else:
                current_part += line + "\n"

        if current_part:
            parts.append(current_part)

        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                messages.append(part)
            else:
                messages.append(f"{part}\n\n--- (第 {i + 1}/{len(parts)} 部分) ---")
    else:
        messages.append(content[:MAX_MESSAGE_LENGTH] + "\n\n...(输出过长，已截断)")

    return messages


import dingtalk_stream
from dingtalk_stream import AckMessage

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s %(levelname)-8s %(message)s"
)
logger = logging.getLogger(__name__)

qm = QueueManager(QUEUE_DIR)
CONVERSATIONS = {}
client_instance = None
last_message_time = time.time()
last_ping_time = time.time()
connection_error_count = 0
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5
HEARTBEAT_INTERVAL = 30  # 从60秒改为30秒，更快速检测连接问题
MAX_RETRIES = 3
RETRY_DELAY = 2

_token_cache: Dict[str, Dict[str, Any]] = {
    "token": None,
    "expires_at": None,
    "refresh_at": None,
}
TOKEN_REFRESH_BUFFER = timedelta(minutes=5)
TOKEN_REFRESH_RETRIES = 3
TOKEN_REFRESH_RETRY_DELAY = 2

# 发送失败跟踪
_send_failure_count: Dict[str, int] = {}
_MAX_SEND_FAILURES = 10
_FAILED_RESULT_AGE_LIMIT = timedelta(hours=1)


def retry_on_failure(max_retries=MAX_RETRIES, delay=RETRY_DELAY):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}"
                        )
                        time.sleep(delay * (2**attempt))
            logger.error(
                f"{func.__name__} failed after {max_retries} attempts: {last_exception}"
            )
            raise last_exception

        return wrapper

    return decorator


def validate_token(token: str) -> bool:
    """验证token是否有效"""
    try:
        url = "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend"
        data = {
            "robotCode": CLIENT_ID,
            "userIds": ["dummy"],
            "msgKey": "sampleText",
            "msgParam": json.dumps({"content": "test"}),
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-acs-dingtalk-access-token": token,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        if e.code == 401 or e.code == 403:
            return False
        return True
    except Exception:
        return False


def get_access_token(force_refresh=False):
    global _token_cache

    now = datetime.now()

    # 检查token是否即将过期（提前10分钟警告）
    if (
        _token_cache["expires_at"]
        and now + timedelta(minutes=10) >= _token_cache["expires_at"]
    ):
        logger.warning(
            f"[Token警告] Token即将过期: {_token_cache['expires_at']}, "
            f"剩余时间: {(_token_cache['expires_at'] - now).total_seconds():.0f}秒"
        )

    if not force_refresh and _token_cache["token"]:
        if _token_cache["expires_at"] and now < _token_cache["refresh_at"]:
            return _token_cache["token"]

    # Token刷新重试机制
    last_error = None
    for attempt in range(TOKEN_REFRESH_RETRIES):
        try:
            url = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
            data = json.dumps({"appKey": CLIENT_ID, "appSecret": CLIENT_SECRET}).encode(
                "utf-8"
            )
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                response = json.loads(resp.read().decode("utf-8"))
                token = response.get("accessToken")
                expire_in = response.get("expireIn", 7200)

                if token:
                    _token_cache["token"] = token
                    _token_cache["expires_at"] = now + timedelta(seconds=expire_in)
                    _token_cache["refresh_at"] = (
                        _token_cache["expires_at"] - TOKEN_REFRESH_BUFFER
                    )
                    logger.info(
                        f"[Token刷新] 成功 (尝试 {attempt + 1}/{TOKEN_REFRESH_RETRIES}), "
                        f"过期时间: {_token_cache['expires_at']}"
                    )
                    return token
                else:
                    raise ValueError("No token in response")

        except Exception as e:
            last_error = e
            if attempt < TOKEN_REFRESH_RETRIES - 1:
                logger.warning(
                    f"[Token刷新] 失败 (尝试 {attempt + 1}/{TOKEN_REFRESH_RETRIES}): {e}, "
                    f"{TOKEN_REFRESH_RETRY_DELAY}s后重试..."
                )
                time.sleep(TOKEN_REFRESH_RETRY_DELAY)

    # 所有重试都失败
    if _token_cache["token"]:
        # 验证缓存的token是否仍然有效
        logger.warning("[Token刷新] 所有重试失败，验证缓存的token...")
        if validate_token(_token_cache["token"]):
            logger.info("[Token刷新] 缓存的token仍然有效，继续使用")
            return _token_cache["token"]
        else:
            logger.error("[Token刷新] 缓存的token已失效！")

    logger.error(f"[Token刷新] 所有重试失败: {last_error}")
    raise last_error if last_error else Exception("Token refresh failed")


@retry_on_failure()
def send_group_message(
    conv_id, content, token=None, msg_type="text", title=None, image_key=None
):
    if not token:
        token = get_access_token()

    msg_keys = {
        "text": "sampleText",
        "markdown": "sampleMarkdown",
        "actionCard": "sampleActionCard",
        "image": "sampleImageMsg",
    }

    messages = split_long_message(content, msg_type)
    logger.info(f"[分割] 消息长度: {len(content)} 字符，分为 {len(messages)} 条发送")

    results = []
    for i, msg in enumerate(messages):
        if msg_type == "text":
            msg_param = {"content": msg}
        elif msg_type == "markdown":
            msg_param = {"title": title or "消息", "text": msg}
        elif msg_type == "actionCard":
            msg_param = {"title": title or "消息", "text": msg}
        elif msg_type == "image":
            if not image_key:
                logger.error("[图片] 缺少 imageKey")
                return None
            msg_param = {"photoURL": image_key}
        else:
            msg_param = {"content": msg}

        url = "https://api.dingtalk.com/v1.0/robot/groupMessages/send"
        data = {
            "robotCode": CLIENT_ID,
            "openConversationId": conv_id,
            "msgKey": msg_keys.get(msg_type, "sampleText"),
            "msgParam": json.dumps(msg_param, ensure_ascii=False),
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-acs-dingtalk-access-token": token,
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            results.append(result)
            if len(messages) > 1:
                logger.info(f"[分段] 第 {i + 1}/{len(messages)} 条发送成功")

    return results[0] if results else None


@retry_on_failure()
def send_private_message(
    user_id, content, token=None, msg_type="text", title=None, image_key=None
):
    if not token:
        token = get_access_token()

    msg_keys = {
        "text": "sampleText",
        "markdown": "sampleMarkdown",
        "image": "sampleImageMsg",
    }

    messages = split_long_message(content, msg_type)
    logger.info(f"[分割] 消息长度: {len(content)} 字符，分为 {len(messages)} 条发送")

    results = []
    for i, msg in enumerate(messages):
        if msg_type == "text":
            msg_param = {"content": msg}
        elif msg_type == "markdown":
            msg_param = {"title": title or "消息", "text": msg}
        elif msg_type == "image":
            if not image_key:
                logger.error("[图片] 缺少 imageKey")
                return None
            msg_param = {"photoURL": image_key}
        else:
            msg_param = {"content": msg}

        url = "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend"
        data = {
            "robotCode": CLIENT_ID,
            "userIds": [user_id],
            "msgKey": msg_keys.get(msg_type, "sampleText"),
            "msgParam": json.dumps(msg_param, ensure_ascii=False),
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-acs-dingtalk-access-token": token,
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            results.append(result)
            if len(messages) > 1:
                logger.info(f"[分段] 第 {i + 1}/{len(messages)} 条发送成功")

    return results[0] if results else None


@retry_on_failure()
def upload_media(file_path: str, token=None) -> Optional[str]:
    if not token:
        token = get_access_token()

    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return None

    url = "https://oapi.dingtalk.com/media/upload?access_token=" + token + "&type=image"

    with open(file_path, "rb") as f:
        image_data = f.read()

    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = []
    body.append(f"--{boundary}".encode())
    body.append(
        f'Content-Disposition: form-data; name="media"; filename="{os.path.basename(file_path)}"'.encode()
    )
    body.append(b"Content-Type: image/png")
    body.append(b"")
    body.append(image_data)
    body.append(f"--{boundary}--".encode())

    body_data = b"\r\n".join(body)

    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}

    req = urllib.request.Request(url, data=body_data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        media_id = result.get("media_id")
        if media_id:
            logger.info(f"Media uploaded: {media_id}")
            return media_id
    logger.error(f"Upload failed: {result}")
    return None


class DingTalkHandler(dingtalk_stream.ChatbotHandler):
    async def process(self, callback: dingtalk_stream.CallbackMessage):
        global last_message_time, last_ping_time, connection_error_count

        last_message_time = time.time()
        last_ping_time = time.time()
        connection_error_count = 0

        logger.info(f"[消息接收] 收到新消息 at {datetime.now().strftime('%H:%M:%S')}")

        try:
            msg = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
        except Exception as e:
            logger.error(f"[错误] 解析消息失败: {e}")
            return AckMessage.STATUS_OK, "OK"
        user_id = msg.sender_staff_id or msg.sender_id or ""
        text = msg.text.content.strip() if msg.text else ""
        user_nick = msg.sender_nick or "用户"
        conv_type = msg.conversation_type or "1"
        conv_id = msg.conversation_id or ""

        if not text:
            return AckMessage.STATUS_OK, "OK"
        if user_id not in AUTHORIZED_USERS:
            logger.warning(f"[未授权] {user_id}")
            return AckMessage.STATUS_OK, "OK"

        logger.info(f"[{'群聊' if conv_type == '2' else '单聊'}] {user_nick}: {text}")

        image_paths = []
        try:
            image_list = msg.get_image_list()
            if image_list:
                logger.info(f"[图片] 检测到 {len(image_list)} 张图片")
                for idx, image in enumerate(image_list):
                    logger.info(f"[图片] 图片 {idx + 1}: {image}")
                    image_path = os.path.join(
                        MEDIA_DIR,
                        f"{msg.conversation_id or user_id}_{time.time()}_{idx}.png",
                    )
                    try:
                        if hasattr(image, "download_image"):
                            image_data = image.download_image()
                            with open(image_path, "wb") as f:
                                f.write(image_data)
                            image_paths.append(image_path)
                            logger.info(f"[图片] 保存成功: {image_path}")
                        elif hasattr(image, "media_id"):
                            logger.info(f"[图片] 媒体ID: {image.media_id} - 无法下载")
                        else:
                            logger.warning(f"[图片] 未知图片格式: {dir(image)}")
                    except Exception as e:
                        logger.error(f"[图片] 保存失败: {e}")
            else:
                logger.debug("[图片] 无图片附件")
        except Exception as e:
            logger.error(f"[图片] 处理异常: {e}")

        if conv_type == "2":
            CONVERSATIONS[user_id] = conv_id

        task_data = {"message": text, "images": image_paths}
        task_id = qm.add_task(user_id, user_nick, text, conv_type, conv_id, task_data)
        logger.info(f"[任务] {task_id}")

        self.reply_text(f"收到，处理中...", msg)
        return AckMessage.STATUS_OK, "OK"


def detect_message_type(content: str) -> tuple:
    content_lower = content.lower()

    markdown_indicators = [
        "```",
        "**",
        "##",
        "###",
        "###",
        "* ",
        "- [",
        "[link](",
        "[image]",
        ">",
        "|",
        "---",
    ]

    has_markdown = any(indicator in content for indicator in markdown_indicators)

    if has_markdown:
        title = None
        lines = content.split("\n")
        for line in lines[:5]:
            line = line.strip()
            if line.startswith("#"):
                title = line.lstrip("#").strip()
                break
            elif not title and len(line) > 0 and len(line) < 50:
                title = line

        return "markdown", title

    return "text", None


def result_sender():
    logger.info("结果发送线程启动")
    token = get_access_token()
    sent = set()

    while True:
        try:
            results = qm.get_pending_results()
            logger.info(f"[检查] 待发送结果数: {len(results)}")

            # 定期刷新token
            now = datetime.now()
            if _token_cache["expires_at"] and now >= _token_cache["refresh_at"]:
                logger.info("[Token] 定期刷新token...")
                token = get_access_token(force_refresh=True)

            for task_id, result in results.items():
                # 检查是否长时间发送失败
                created_at_str = result.get("created_at", "")
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        if now - created_at > _FAILED_RESULT_AGE_LIMIT:
                            failure_count = _send_failure_count.get(task_id, 0)
                            if failure_count >= _MAX_SEND_FAILURES:
                                logger.error(
                                    f"[清理] 任务 {task_id} 已失败 {failure_count} 次，"
                                    f"已超时 {_FAILED_RESULT_AGE_LIMIT}，自动清理"
                                )
                                qm.clear_result(task_id)
                                if task_id in _send_failure_count:
                                    del _send_failure_count[task_id]
                                if task_id in sent:
                                    sent.remove(task_id)
                                continue
                    except Exception as e:
                        logger.debug(f"[清理检查] 解析时间失败: {e}")

                if task_id in sent:
                    logger.debug(f"[跳过] 已发送: {task_id}")
                    continue

                response = result.get("response", "")
                conv_id = result.get("conv_id", "")
                user_id = result.get("user_id", "")
                conv_type = result.get("conv_type", "1")
                images = result.get("images", [])

                logger.info(
                    f"[处理] task_id={task_id}, user_id={user_id}, response={response[:100] if response else 'empty'}"
                )

                send_success = False

                msg_type, msg_title = detect_message_type(response)
                logger.info(
                    f"[消息类型] {msg_type}"
                    + (f", 标题: {msg_title}" if msg_title else "")
                )

                if conv_type == "2":
                    if conv_id:
                        if images:
                            logger.info(f"[工作截图] 发现 {len(images)} 张相关工作截图")
                            for img_path in images:
                                if os.path.exists(img_path):
                                    logger.info(f"[工作截图] 上传: {img_path}")
                                    media_id = upload_media(img_path, token)
                                    if media_id:
                                        send_result = send_group_message(
                                            conv_id, "", token, "image", None, media_id
                                        )
                                        logger.info(
                                            f"[工作截图] 发送成功: {send_result}"
                                        )
                                        send_success = send_result is not None
                                        break
                        else:
                            logger.info(f"[群聊] 发送文字消息，长度: {len(response)}")
                            send_result = send_group_message(
                                conv_id, response, token, msg_type, msg_title
                            )
                            logger.info(f"[群聊] 钉钉API返回: {send_result}")
                            send_success = send_result is not None
                    else:
                        logger.error(f"[群聊] 无conversation_id: {task_id}")
                else:
                    logger.info(f"[私聊] 发送到钉钉: user_id={user_id}")
                    if images:
                        logger.info(f"[工作截图] 发现 {len(images)} 张相关工作截图")
                        for img_path in images:
                            if os.path.exists(img_path):
                                logger.info(f"[工作截图] 上传: {img_path}")
                                media_id = upload_media(img_path, token)
                                if media_id:
                                    send_result = send_private_message(
                                        user_id, "", token, "image", None, media_id
                                    )
                                    logger.info(f"[工作截图] 发送成功: {send_result}")
                                    send_success = send_result is not None
                                    break
                    else:
                        logger.info(f"[私聊] 发送文字消息，长度: {len(response)}")
                        send_result = send_private_message(
                            user_id, response, token, msg_type, msg_title
                        )
                        logger.info(f"[私聊] 钉钉API返回: {send_result}")
                        send_success = send_result is not None

                if send_success:
                    logger.info(f"[成功] 清除结果: task_id={task_id}")
                    qm.clear_result(task_id)
                    sent.add(task_id)
                    # 清除失败计数
                    if task_id in _send_failure_count:
                        del _send_failure_count[task_id]
                else:
                    _send_failure_count[task_id] = (
                        _send_failure_count.get(task_id, 0) + 1
                    )
                    failure_count = _send_failure_count[task_id]
                    logger.error(
                        f"[失败] 发送失败: task_id={task_id}, "
                        f"失败次数: {failure_count}/{_MAX_SEND_FAILURES}"
                    )

        except Exception as e:
            logger.error(f"发送异常: {e}")
            import traceback

            traceback.print_exc()

        time.sleep(2)


def health_check():
    """健康检查线程，定期验证token状态"""
    logger.info("[健康检查] 健康检查线程启动")

    while True:
        try:
            time.sleep(300)  # 每5分钟检查一次

            now = datetime.now()

            # 检查token状态
            if _token_cache["token"]:
                if _token_cache["expires_at"]:
                    time_to_expire = (_token_cache["expires_at"] - now).total_seconds()

                    if time_to_expire < 0:
                        logger.error("[健康检查] Token已过期！")
                    elif time_to_expire < 600:  # 小于10分钟
                        logger.warning(
                            f"[健康检查] Token即将过期: {int(time_to_expire)}秒后过期"
                        )
                    elif time_to_expire < 3600:  # 小于1小时
                        logger.info(
                            f"[健康检查] Token有效期: {int(time_to_expire / 60)}分钟"
                        )

                    # 检查是否需要刷新
                    if now >= _token_cache["refresh_at"]:
                        logger.info("[健康检查] 触发token刷新...")
                        try:
                            get_access_token(force_refresh=True)
                        except Exception as e:
                            logger.error(f"[健康检查] Token刷新失败: {e}")

            # 检查堆积的结果
            results = qm.get_pending_results()
            if len(results) > 10:
                logger.warning(
                    f"[健康检查] 待发送结果过多: {len(results)}，可能存在发送问题"
                )

            # 检查发送失败的任务
            stale_results = []
            for task_id, result in results.items():
                created_at_str = result.get("created_at", "")
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        if now - created_at > _FAILED_RESULT_AGE_LIMIT:
                            stale_results.append((task_id, created_at))
                    except:
                        pass

            if stale_results:
                logger.warning(
                    f"[健康检查] 发现 {len(stale_results)} 个超时结果，"
                    f"最旧的已超过 {(now - stale_results[0][1]).total_seconds() / 3600:.1f} 小时"
                )

        except Exception as e:
            logger.error(f"[健康检查] 异常: {e}")


def heartbeat_monitor():
    global last_message_time, last_ping_time, connection_error_count

    logger.info("心跳监控线程启动")

    while True:
        try:
            time.sleep(HEARTBEAT_INTERVAL)

            time_since_last_msg = time.time() - last_message_time
            time_since_last_ping = time.time() - last_ping_time

            # 记录心跳状态
            logger.info(
                f"[心跳检查] 消息间隔: {int(time_since_last_msg)}s, "
                f"ping间隔: {int(time_since_last_ping)}s, "
                f"错误计数: {connection_error_count}/{MAX_RECONNECT_ATTEMPTS}"
            )

            # 检查是否长时间没有消息
            if time_since_last_msg > HEARTBEAT_INTERVAL * 3:
                connection_error_count += 1
                logger.warning(
                    f"[心跳警告] 已 {int(time_since_last_msg)}s 未收到消息 (错误计数: {connection_error_count})"
                )

                if connection_error_count >= MAX_RECONNECT_ATTEMPTS:
                    logger.error(
                        f"[心跳超时] {MAX_RECONNECT_ATTEMPTS} 次心跳失败，触发重连"
                    )
                    force_reconnect()
                    connection_error_count = 0
            else:
                logger.debug(f"[心跳正常] 最后消息 {int(time_since_last_msg)}s 前")

            # 如果超过5分钟没有任何活动（消息或ping），也触发重连
            max_idle_time = max(time_since_last_msg, time_since_last_ping)
            if max_idle_time > 300:  # 5分钟
                connection_error_count += 1
                logger.warning(
                    f"[空闲超时] 已 {int(max_idle_time)}s 无任何活动，触发重连 (错误计数: {connection_error_count})"
                )
                if connection_error_count >= 3:  # 3次后强制重连
                    force_reconnect()
                    connection_error_count = 0

        except Exception as e:
            logger.error(f"心跳监控异常: {e}")


def force_reconnect():
    global client_instance

    logger.warning("[重连] 开始重连钉钉服务...")

    try:
        if client_instance:
            logger.info("[重连] 停止旧连接...")
            try:
                client_instance.stop()
            except:
                pass

        time.sleep(2)

        logger.info("[重连] 创建新连接...")
        credential = dingtalk_stream.Credential(CLIENT_ID, CLIENT_SECRET)
        client_instance = dingtalk_stream.DingTalkStreamClient(credential)
        client_instance.register_callback_handler(
            dingtalk_stream.chatbot.ChatbotMessage.TOPIC, DingTalkHandler()
        )

        logger.info("[重连] 启动连接...")
        client_instance.start_forever()

    except Exception as e:
        logger.error(f"[重连失败] {e}")
        raise


def run_with_reconnect():
    global client_instance, connection_error_count

    logger.info("=" * 50)
    logger.info("OpenCode 钉钉网关启动")
    logger.info(f"队列目录: {QUEUE_DIR}")
    logger.info(f"心跳间隔: {HEARTBEAT_INTERVAL}s")
    logger.info(f"最大重连尝试: {MAX_RECONNECT_ATTEMPTS}")
    logger.info(f"Token刷新缓冲: {TOKEN_REFRESH_BUFFER}")
    logger.info(f"空闲超时阈值: 300s")
    logger.info("=" * 50)

    threading.Thread(target=result_sender, daemon=True).start()
    threading.Thread(target=heartbeat_monitor, daemon=True).start()
    threading.Thread(target=health_check, daemon=True).start()

    retry_count = 0

    while True:
        try:
            logger.info(
                f"[连接] 尝试连接 (尝试 {retry_count + 1}/{MAX_RECONNECT_ATTEMPTS})"
            )

            credential = dingtalk_stream.Credential(CLIENT_ID, CLIENT_SECRET)
            client_instance = dingtalk_stream.DingTalkStreamClient(credential)
            client_instance.register_callback_handler(
                dingtalk_stream.chatbot.ChatbotMessage.TOPIC, DingTalkHandler()
            )

            logger.info("[连接] 连接中...")
            client_instance.start_forever()
            retry_count = 0

        except KeyboardInterrupt:
            logger.info("[停止] 收到中断信号，退出")
            break

        except Exception as e:
            retry_count += 1
            connection_error_count += 1
            logger.error(f"[连接异常] {e}")
            logger.error(
                f"[重连] {retry_count}/{MAX_RECONNECT_ATTEMPTS}，{RECONNECT_DELAY}s 后重试..."
            )

            if retry_count < MAX_RECONNECT_ATTEMPTS:
                time.sleep(RECONNECT_DELAY)
            else:
                logger.error(
                    f"[退出] 达到最大重连次数，等待 {RECONNECT_DELAY * 2}s 后继续尝试"
                )
                time.sleep(RECONNECT_DELAY * 2)
                retry_count = 0


def main():
    run_with_reconnect()


if __name__ == "__main__":
    main()
