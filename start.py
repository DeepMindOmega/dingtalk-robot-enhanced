#!/usr/bin/env python3
import subprocess
import sys
import os
import time

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    print("=" * 50)
    print("OpenCode 钉钉机器人插件")
    print("=" * 50)

    gateway = subprocess.Popen([sys.executable, f"{SKILL_DIR}/src/gateway.py"])
    processor = subprocess.Popen([sys.executable, f"{SKILL_DIR}/src/processor.py"])

    print("✓ 网关已启动")
    print("✓ 处理器已启动")
    print("\n在钉钉发消息给机器人测试！")
    print("按 Ctrl+C 退出\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止...")
        gateway.terminate()
        processor.terminate()
        print("已退出")


if __name__ == "__main__":
    main()
