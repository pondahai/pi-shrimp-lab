import urllib.request
import json
import sys
import os
os.environ["GPIOZERO_PIN_FACTORY"] = "lgpio"
import os
import base64
import subprocess
import threading
import time
import queue
import numpy as np
import sounddevice as sd
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from gpiozero import Button

# 檢查是否為純文字模式
TEXT_ONLY_MODE = os.environ.get("XIAOPAI_TEXT_ONLY") == "1"
if TEXT_ONLY_MODE:
    print("\n[DEBUG] 檢測到純文字模式環境變數：XIAOPAI_TEXT_ONLY=1")

# 載入語音引擎
if not TEXT_ONLY_MODE:
    print("正在載入語音辨識模型 (Whisper)...")
    try:
        from faster_whisper import WhisperModel
        whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    except Exception as e:
        print("載入 Whisper 失敗:", e)
        whisper_model = None

    print("正在載入語音合成模型 (Sherpa-ONNX)...")
    try:
        import sherpa_onnx
        tts_config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model="/home/pi/xiaopai4/model_files/breeze-custom/breeze2-vits.onnx",
                    lexicon="/home/pi/xiaopai4/model_files/breeze-custom/lexicon.txt",
                    tokens="/home/pi/xiaopai4/model_files/breeze-custom/tokens.txt",
                    noise_scale=0.333,
                    noise_scale_w=0.2,
                    length_scale=1.1
                )
            )
        )
        tts = sherpa_onnx.OfflineTts(tts_config)
    except Exception as e:
        print("載入 Sherpa-ONNX 失敗:", e)
        tts = None
else:
    print("📢 小派以【純文字模式】啟動 (已停用語音辨識與合成)")
    whisper_model = None
    tts = None

# --- OLED ---
class OledDisplay:
    def __init__(self):
        self.serial = i2c(port=1, address=0x3C)
        self.device = ssd1306(self.serial)
        self.font = ImageFont.truetype("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 12)
        self.width = self.device.width
        self.height = self.device.height
        self.line_height = 14
        self.max_lines = self.height // self.line_height
        self.history = []

    def draw_screen(self, current_text=""):
        image = Image.new("1", (self.width, self.height))
        draw = ImageDraw.Draw(image)
        
        display_lines = []
        for role, msg in self.history[-1:]:
            prefix = "你: " if role == "user" else "小派: "
            full_msg = prefix + msg
            current_line = ""
            for char in full_msg:
                test_line = current_line + char
                bbox = draw.textbbox((0, 0), test_line, font=self.font)
                if bbox[2] - bbox[0] > self.width:
                    display_lines.append(current_line)
                    current_line = char
                else:
                    current_line = test_line
            if current_line:
                display_lines.append(current_line)
                
        if current_text:
            full_msg = "小派: " + current_text
            current_line = ""
            for char in full_msg:
                test_line = current_line + char
                bbox = draw.textbbox((0, 0), test_line, font=self.font)
                if bbox[2] - bbox[0] > self.width:
                    display_lines.append(current_line)
                    current_line = char
                else:
                    current_line = test_line
            if current_line:
                display_lines.append(current_line)

        display_lines = display_lines[-self.max_lines:]
        y = 0
        for line in display_lines:
            draw.text((0, y), line, font=self.font, fill=255)
            y += self.line_height
        self.device.display(image)

    def show_message(self, text):
        image = Image.new("1", (self.width, self.height))
        draw = ImageDraw.Draw(image)
        draw.text((10, 25), text, font=self.font, fill=255)
        self.device.display(image)

print("正在喚醒小派的 OLED 螢幕與 GPIO...")
try:
    oled = OledDisplay()
    oled.show_message("小派系統啟動中...")
except Exception as e:
    print("OLED 初始化失敗:", e)
    sys.exit(1)

import datetime
import subprocess

def get_current_time():
    now = datetime.datetime.now()
    return f"現在時間是：{now.strftime('%Y年%m月%d日 %H:%M:%S')}"

def get_system_status():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = float(f.read().strip()) / 1000.0
        # try to use free -m
        result = subprocess.run(['free', '-m'], capture_output=True, text=True)
        return f"CPU溫度: {temp:.1f}°C\n記憶體狀態:\n{result.stdout.strip()}"
    except Exception as e:
        return f"讀取系統狀態失敗: {e}"

def execute_shell_command(command):
    allowlist = ['ls', 'ping', 'df', 'uptime', 'free', 'curl']
    cmd_base = command.split()[0] if command else ""
    if cmd_base not in allowlist:
        return f"安全限制：不允許執行指令 '{cmd_base}'，只允許: {', '.join(allowlist)}"
    try:
        # 過濾 curl 指令，只允許特定的天氣或 API 查詢，防止隨意下載腳本
        if cmd_base == 'curl' and 'wttr.in' not in command and 'api' not in command:
            return "安全限制：curl 只允許用於天氣或 API 查詢。"
            
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        return (result.stdout + result.stderr).strip()[:800]
    except Exception as e:
        return f"指令執行失敗: {e}"

SYSTEM_PROMPT = """你是「小派」，一個運行在樹莓派 5 上的 AI 代理。你可以思考、操作工具並與人溫暖地對話。

### 互動規範：
1. **工具呼叫 (內部任務)**：當你需要執行工具（如拍照、查時間、查系統）時，請【必須】輸出一個 JSON 物件，格式如下：
   {
     "thought": "你的思考過程",
     "tool_name": "工具名稱",
     "tool_args": "參數"
   }

2. **最終回答 (對人對話)**：當你已經取得所需的資訊，或者只是在跟我聊天時，請【不要使用 JSON】，直接以「自然、簡短、口語化」的繁體中文回答我（字數請控制在 50 字內）。

可用的工具 (tool_name)：
- "get_current_time": 獲取現在時間
- "get_system_status": 獲取 CPU 溫度與記憶體狀態
- "capture_and_analyze_vision": 拍照並觀看眼前畫面
- "execute_shell_command": 執行終端機安全指令 (參數 command 為指令字串)
"""

initial_messages = [
    {"role": "system", "content": SYSTEM_PROMPT}
]
messages = list(initial_messages)

def normalize_for_tts(text):
    import re
    # 1. 移除 Emoji 與特殊符號 (保留基本標點)
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。！？、 ]', '', text)
    
    # 2. 數字轉中文 (處理 0-99 的簡單邏輯，適合氣溫、時間)
    def num_replace(match):
        num = int(match.group())
        cn_nums = "零一二三四五六七八九"
        if num < 10:
            return cn_nums[num]
        elif num < 20:
            return "十" + (cn_nums[num % 10] if num % 10 != 0 else "")
        elif num < 100:
            return cn_nums[num // 10] + "十" + (cn_nums[num % 10] if num % 10 != 0 else "")
        return str(num) # 超過 100 暫不處理

    text = re.sub(r'\d+', num_replace, text)
    
    # 3. 英文特定詞彙轉換
    text = text.replace("AI", "欸哀").replace("CPU", "希披優")
    
    return text

# --- 錄音與按鍵邏輯 ---
is_recording = False
audio_data = []

def trigger_menu_exit():
    print("\n[系統] 偵測到長按 4 秒，準備跳回選單...")
    oled.show_message("正在呼叫選單...")
    # 停止所有背景活動
    global is_recording
    is_recording = False
    # 這裡使用 os._exit 強制退出，避免被 try-except 攔截
    os._exit(88) 

def record_audio_callback(indata, frames, time_info, status):
    if is_recording:
        audio_data.append(indata.copy())

rec_stream = None

def start_recording():
    global is_recording, audio_data, rec_stream
    audio_data = []
    is_recording = True
    try:
        if rec_stream is None:
            rec_stream = sd.InputStream(samplerate=48000, channels=1, callback=record_audio_callback)
            rec_stream.start()
    except Exception as e:
        print("開啟麥克風失敗:", e)
    oled.show_message("正在聆聽...\n(放開按鍵結束)")
    print("\n[系統] 開始錄音... (放開按鍵結束錄音)")

def stop_recording():
    global is_recording, audio_data, rec_stream
    if not is_recording: return None # 如果已經因為長按被關閉則忽略
    is_recording = False
    if rec_stream is not None:
        rec_stream.stop()
        rec_stream.close()
        rec_stream = None
    oled.show_message("處理語音中...")
    print("\n[系統] 結束錄音，正在處理...")
    if len(audio_data) > 0:
        recording = np.concatenate(audio_data, axis=0)
        return recording
    return None

input_queue = queue.Queue()
btn_press_time = 0
click_times = []

def trigger_menu_exit():
    print("\n[系統] 偵測到三連擊，準備跳回選單...")
    oled.show_message("正在呼叫選單...")
    global is_recording
    is_recording = False
    os._exit(88)

def button_pressed():
    global btn_press_time
    btn_press_time = time.time()
    if not TEXT_ONLY_MODE:
        start_recording()
    else:
        print("\n[系統] 目前為純文字模式，語音錄音已停用。")

def button_released():
    global btn_press_time, click_times
    now = time.time()
    duration = now - btn_press_time
    
    # 紀錄點擊時間點，用於連擊判定
    click_times.append(now)
    # 只保留最近 3 次點擊，且必須在 1.2 秒內完成
    click_times = [t for t in click_times if now - t < 1.2]
    
    if len(click_times) >= 3:
        trigger_menu_exit()
        return

    # 原有的錄音與清除記憶邏輯
    if duration > 3.5: # 視為長按結束（錄音已由 start_recording 處理）
        stop_recording()
        return

    if TEXT_ONLY_MODE:
        if duration < 0.5:
            input_queue.put(("[CLEAR]", None))
        return

    recording = stop_recording()
    if duration < 0.5:
        input_queue.put(("[CLEAR]", None))
    else:
        if whisper_model and recording is not None and len(recording) > 48000 * 0.5:
            try:
                sf.write("/tmp/temp_record.wav", recording, 48000)
                segments, _ = whisper_model.transcribe("/tmp/temp_record.wav", language="zh")
                text = "".join([segment.text for segment in segments])
                if text.strip():
                    input_queue.put((text.strip(), "voice"))
                else:
                    oled.show_message("聽不清楚，請再試一次。")
            except Exception as e:
                print("語音處理錯誤:", e)
        else:
            oled.draw_screen()

try:
    btn = Button(22, pull_up=True, bounce_time=0.1)
    # 移除 when_held 退出，將其留給語音錄音或未來擴充
    btn.when_pressed = button_pressed
    btn.when_released = button_released
except Exception as e:
    print("按鍵初始化失敗:", e)

# (錄音串流改為按鍵時動態開啟)

def capture_image_base64():
    print("[系統] 正在拍攝照片...")
    oled.show_message("正在拍攝照片...")
    img_path = "/home/pi/vision_temp.jpg"
    try:
        subprocess.run(['rpicam-jpeg', '-o', img_path, '-t', '1000', '--width', '640', '--height', '480'], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        with open(img_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")
    except Exception as e:
        print(f"拍攝失敗: {e}")
        return None

def keyboard_thread():
    while True:
        try:
            text = input("\n你: ")
            if text.strip():
                input_queue.put((text, "text"))
        except EOFError:
            break

def pipe_thread():
    pipe_path = "/tmp/xiaopai_input"
    if not os.path.exists(pipe_path):
        os.mkfifo(pipe_path)
    
    while True:
        try:
            # 使用低階 os.open 以讀寫模式開啟管道，防止阻塞
            fd = os.open(pipe_path, os.O_RDWR)
            with os.fdopen(fd, 'r') as fifo:
                while True:
                    line = fifo.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    text = line.strip()
                    if text:
                        print(f"\n[終端輸入] {text}")
                        input_queue.put((text, "terminal"))
        except Exception as e:
            time.sleep(1)

threading.Thread(target=keyboard_thread, daemon=True).start()
threading.Thread(target=pipe_thread, daemon=True).start()

print("==================================================")
print("    🧠 啟動「小派」的大腦 (Gemma + 視覺 + 語音 + OLED)... ")
print("==================================================")
print("小派：你好！我是小派，我現在可以聽、說、看了！")
print("(輸入 exit 即可離開)")
print("(💡 提示：短按 GPIO22 清除記憶；長按 GPIO22 說話！)")
print("(💡 提示：輸入「看」或「拍照」，小派就會張開眼睛看著你！)")
print("--------------------------------------------------")

oled.show_message("小派準備就緒！\n等待你的訊息...")

while True:
    try:
        user_input, input_type = input_queue.get()
        
        if user_input == "[CLEAR]":
            messages = list(initial_messages)
            oled.history.append(("user", "[按鍵清除記憶]"))
            oled.draw_screen(current_text="記憶已清除！\n我們可以重新開始聊天。")
            print("\n[系統] 偵測到按鍵！對話記憶已清除。")
            continue
            
        if user_input.lower() in ['exit', 'quit']:
            oled.show_message("小派休息囉！Zzz")
            break
            
        if input_type == "voice":
            print(f"你 (語音): {user_input}")
            
        messages.append({"role": "user", "content": user_input})
        oled.history.append(("user", user_input))
        oled.draw_screen()
        
        # Agent Loop
        agent_loop_count = 0
        while agent_loop_count < 5:
            agent_loop_count += 1
            
            payload = {
                "messages": messages,
                "stream": False,
                "temperature": 0.6,
                "max_tokens": 1024
            }
            
            headers = {"Content-Type": "application/json"}
            if os.environ.get("USE_CLOUD_LLM") == "1":
                api_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
                headers["Authorization"] = "Bearer "
                api_key = os.environ.get("GEMINI_API_KEY", "")
                headers["x-goog-api-key"] = api_key
                payload["model"] = "models/gemma-4-31b-it"
            else:
                api_url = "http://127.0.0.1:8080/v1/chat/completions"
            
            print("小派: (思考中...)", end="", flush=True)
            oled.draw_screen(current_text="(思考中...)")
            
            try:
                raw_response = ""
                if os.environ.get("USE_CLOUD_LLM") == "1":
                    import subprocess
                    curl_cmd = [
                        "curl", "-s", "-X", "POST",
                        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                        "-H", "Content-Type: application/json",
                        "-H", "Authorization: Bearer ",
                        "-H", "x-goog-api-key: " + api_key,
                        "-d", json.dumps(payload)
                    ]
                    result = subprocess.run(curl_cmd, capture_output=True, text=True)
                    raw_response = result.stdout
                else:
                    data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(api_url, data=data, headers=headers)
                    with urllib.request.urlopen(req, timeout=600) as response:
                        raw_response = response.read().decode("utf-8")
                        
                if not raw_response.strip():
                    print("\n[系統] 錯誤: 大腦回傳了空白訊息。可能是模型崩潰或處理失敗。")
                    break

                res_body = json.loads(raw_response)
                
                # 防禦性檢查
                if not isinstance(res_body, dict):
                    print(f"\n[系統] 錯誤: API 回傳並非 JSON 物件。內容: {raw_response}")
                    break

                if "choices" not in res_body or len(res_body["choices"]) == 0:
                    if "error" in res_body:
                        print(f"\n[大腦回傳錯誤]: {res_body['error'].get('message', '未知錯誤')}")
                    else:
                        print(f"\n[系統] 錯誤: API 回傳內容中找不到 choices。完整內容: {raw_response}")
                    break
                    
                choice_msg = res_body["choices"][0].get("message", {})
                response_text = choice_msg.get("content", "")
                
                # 如果 content 為空，檢查是否被安全過濾
                if not response_text:
                    finish_reason = res_body["choices"][0].get("finish_reason")
                    print(f"\n[系統] 警告: 模型未回傳文字 (原因: {finish_reason})")
                    if finish_reason == "safety":
                        print("[提示] 回應被安全過濾器攔截。")
                    else:
                        print(f"DEBUG 完整回傳: {raw_response}")
                    break
                
                # Filter out <thought>...</thought> tags
                import re
                thoughts = re.findall(r"<thought>(.*?)</thought>", response_text, flags=re.DOTALL)
                if thoughts:
                    print(f"\n[大腦思考過程]: {thoughts[0].strip()}")
                
                clean_response = re.sub(r"<thought>.*?</thought>", "", response_text, flags=re.DOTALL).strip()
                
                # 彈性解析：嘗試辨識 JSON 或 純文字
                agent_response = {}
                is_json = False
                
                # 嘗試清除 Markdown 標籤以尋找 JSON
                potential_json = clean_response
                if "```json" in potential_json:
                    match = re.search(r"```json\s*(.*?)\s*```", potential_json, re.DOTALL)
                    if match:
                        potential_json = match.group(1)
                
                try:
                    parsed = json.loads(potential_json)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        parsed = parsed[0]
                    if isinstance(parsed, dict):
                        agent_response = parsed
                        is_json = True
                except:
                    is_json = False

                if is_json and agent_response.get("tool_name"):
                    # 如果是工具呼叫
                    tool_name = agent_response.get("tool_name", "")
                    tool_args = agent_response.get("tool_args", "")
                    
                    messages.append({"role": "assistant", "content": response_text})
                    
                    print(f"\n[系統] 正在呼叫工具: {tool_name}({tool_args})")
                    oled.draw_screen(current_text=f"呼叫 {tool_name}...")
                    
                    tool_result = ""
                    if tool_name == "get_current_time":
                        tool_result = get_current_time()
                    elif tool_name == "get_system_status":
                        tool_result = get_system_status()
                    elif tool_name == "capture_and_analyze_vision":
                        base64_img = capture_image_base64()
                        if base64_img:
                            tool_result = "已獲取照片，請分析畫面。"
                            messages.append({"role": "user", "content": [
                                {"type": "text", "text": tool_result},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                            ]})
                        else:
                            tool_result = "拍照失敗。"
                            messages.append({"role": "system", "content": tool_result})
                    elif tool_name == "execute_shell_command":
                        tool_result = execute_shell_command(tool_args)
                    else:
                        tool_result = f"找不到工具: {tool_name}"
                        
                    print(f"[系統] 工具結果:\n{tool_result}")
                    if tool_name != "capture_and_analyze_vision":
                        messages.append({"role": "user", "content": f"工具 {tool_name} 的執行結果:\n{tool_result}"})
                    
                    continue
                else:
                    # 如果是純文字回答 (或是 JSON 裡的 message 內容)
                    if is_json and "message" in agent_response:
                        message_text = agent_response["message"]
                    elif is_json and not agent_response.get("tool_name"):
                        # 如果是 JSON 但沒 tool_name，嘗試找其他可能的回答欄位
                        message_text = None
                        for fk in ["answer", "summary", "analysis", "content", "response"]:
                            if fk in agent_response:
                                message_text = str(agent_response[fk])
                                break
                        if not message_text:
                            message_text = clean_response
                    else:
                        # 這是大腦回傳的自然語言
                        message_text = clean_response
                    
                    if not str(message_text).strip():
                        print(f"\n[系統] 模型未回傳有效文字。原始內容: {response_text}")
                        break

                    messages.append({"role": "assistant", "content": response_text})
                    print(f"\r\033[K小派: {message_text}", flush=True)
                    oled.draw_screen(current_text=message_text)
                    
                    # 語音合成輸出
                    if not TEXT_ONLY_MODE and tts and str(message_text).strip():
                        try:
                            speak_text = normalize_for_tts(str(message_text))
                            print(f"[語音同步] {speak_text}")
                            audio = tts.generate(speak_text)
                            if audio and len(audio.samples) > 0:
                                sd.default.device = None
                                original_sr = audio.sample_rate
                                target_sr = 48000
                                if original_sr != target_sr:
                                    duration = len(audio.samples) / original_sr
                                    target_length = int(duration * target_sr)
                                    x_old = np.linspace(0, duration, len(audio.samples))
                                    x_new = np.linspace(0, duration, target_length)
                                    resampled_audio = np.interp(x_new, x_old, audio.samples)
                                    amplified_audio = resampled_audio * 8.0
                                    sd.play(amplified_audio, target_sr)
                                else:
                                    amplified_audio = np.array(audio.samples) * 8.0
                                    sd.play(amplified_audio, audio.sample_rate)
                                sd.wait()
                        except Exception as e:
                            print("\n播放語音失敗:", e)
                    break 
                        
            except urllib.error.HTTPError as e:
                error_msg = e.read().decode("utf-8")
                print(f"\n[大腦回傳錯誤]: {e.code} - {error_msg}")
                if "image" in error_msg.lower() or e.code == 400:
                    print("[系統提示] 模型可能尚未正確載入視覺投影檔 (mmproj)。")
                    messages.pop()
                break
            except Exception as e:
                print(f"\n[內部錯誤]: {e}")
                break
        
    except KeyboardInterrupt:
        oled.show_message("小派休息囉！Zzz")
        break
    except Exception as e:
        print(f"\n錯誤: {e}")
        oled.show_message("連線到大腦失敗 :(")
