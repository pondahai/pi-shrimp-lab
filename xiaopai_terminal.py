import os
import sys
import subprocess
import threading
import time

# 設定管道路徑
PIPE_PATH = "/tmp/xiaopai_input"

import re

def monitor_logs():
    """背景執行緒：監控系統日誌並提取小派的回答"""
    # 使用 journalctl -a 強制顯示所有文字內容，避免 [blob data]
    cmd = ["journalctl", "-u", "xiaopai", "-n", "0", "-f", "-a", "--no-pager"]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                               text=True, encoding='utf-8', errors='ignore')
    
    # 用來移除 ANSI 顏色代碼與 \r\033[K 的正則
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])|\r')

    try:
        for line in process.stdout:
            # 移除日誌頭部與 ANSI 代碼
            clean_line = ansi_escape.sub('', line).strip()
            
            # 尋找小派的正式回覆 (過濾掉「思考中」)
            if "小派:" in clean_line and "(思考中" not in clean_line:
                # 提取「小派: 」之後的內容
                try:
                    content = clean_line.split("小派:")[1].strip()
                    if content:
                        print(f"\r\033[K\033[1;32m小派：{content}\033[0m")
                        print("\n你: ", end="", flush=True)
                except IndexError:
                    pass
            elif "正在呼叫工具" in clean_line:
                try:
                    tool = clean_line.split("正在呼叫工具:")[1].strip()
                    print(f"\r\033[K\033[1;33m[系統] 正在呼叫工具: {tool}\033[0m")
                except IndexError:
                    pass
    finally:
        process.terminate()

def main():
    if not os.path.exists(PIPE_PATH):
        print("錯誤：小派後台服務似乎未啟動（找不到 /tmp/xiaopai_input）。")
        return

    print("==================================================")
    print("    🍓 小派 (Xiaopai) 終端控制台")
    print("    輸入訊息後按 Enter 發送，輸入 'exit' 離開")
    print("==================================================")

    # 啟動日誌監控執行緒
    log_thread = threading.Thread(target=monitor_logs, daemon=True)
    log_thread.start()

    time.sleep(1) # 等待日誌連接

    try:
        while True:
            user_input = input("你: ")
            if user_input.lower() in ['exit', 'quit']:
                break
            
            if user_input.strip():
                # 寫入管道
                try:
                    with open(PIPE_PATH, "w") as fifo:
                        fifo.write(user_input + "\n")
                except Exception as e:
                    print(f"發送失敗: {e}")
    except EOFError:
        pass
    except KeyboardInterrupt:
        pass
    print("\n退出控制台。")

if __name__ == "__main__":
    main()
