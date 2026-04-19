import os
import sys
import subprocess
import threading
import time

# 設定管道路徑
PIPE_PATH = "/tmp/xiaopai_input"

def monitor_logs():
    """背景執行緒：監控系統日誌並提取小派的回答"""
    # 使用 journalctl 監控 xiaopai 服務，只看最新的輸出行
    cmd = ["journalctl", "-u", "xiaopai", "-n", "0", "-f", "--no-pager"]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    try:
        for line in process.stdout:
            # 尋找包含「小派: 」或「[系統]」或「[大腦思考]」的行（可根據需要調整）
            if "小派:" in line:
                # 提取「小派: 」之後的文字
                content = line.split("小派:")[1].strip()
                print(f"\r\033[K\033[1;32m小派：{content}\033[0m") # 綠色輸出
                print("\n你: ", end="", flush=True)
            elif "正在呼叫工具" in line:
                tool = line.split("正在呼叫工具:")[1].strip()
                print(f"\r\033[K\033[1;33m[系統] 正在呼叫工具: {tool}\033[0m")
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
