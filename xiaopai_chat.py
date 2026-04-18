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

# 載入語音引擎
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
    allowlist = ['ls', 'ping', 'df', 'uptime', 'free']
    cmd_base = command.split()[0] if command else ""
    if cmd_base not in allowlist:
        return f"安全限制：不允許執行指令 '{cmd_base}'，只允許: {', '.join(allowlist)}"
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=5)
        return result.stdout.strip()[:500] # 避免輸出過長
    except Exception as e:
        return f"指令執行失敗: {e}"

SYSTEM_PROMPT = """你是「小派」，一個運行在樹莓派 5 上的 AI 代理。你可以思考並使用工具。
你【必須】且【只能】使用以下 JSON 格式回覆：
{
  "thought": "你的內心思考過程（為什麼需要使用工具，或者為什麼現在可以直接回答）",
  "tool_name": "你要呼叫的工具名稱（若不需使用工具，請填 null 或空字串）",
  "tool_args": "工具參數（若無則填空字串）",
  "message": "你要說出的最終回答，字數需少於 30 字，口語化繁體中文（若你正在呼叫工具，請填空字串）"
}

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

# --- 錄音與按鍵邏輯 ---
is_recording = False
audio_data = []

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
            # Google VoiceHAT 僅支援 48000Hz 錄音與播放
            rec_stream = sd.InputStream(samplerate=48000, channels=1, callback=record_audio_callback)
            rec_stream.start()
    except Exception as e:
        print("開啟麥克風失敗:", e)
    oled.show_message("正在聆聽...\n(放開按鍵結束)")
    print("\n[系統] 開始錄音... (放開按鍵結束錄音)")

def stop_recording():
    global is_recording, audio_data, rec_stream
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

def button_pressed():
    global btn_press_time
    btn_press_time = time.time()
    start_recording()

def button_released():
    global btn_press_time
    duration = time.time() - btn_press_time
    recording = stop_recording()
    
    if duration < 0.5:
        input_queue.put(("[CLEAR]", None))
    else:
        # 錄音取樣率為 48000Hz，判斷長度是否大於 0.5 秒
        if whisper_model and recording is not None and len(recording) > 48000 * 0.5:
            try:
                sf.write("/tmp/temp_record.wav", recording, 48000)
                # Whisper 會自動將讀取的音訊重採樣為其需要的 16000Hz
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
            print("你: ", end="", flush=True)

try:
    btn = Button(22, pull_up=True, bounce_time=0.1)
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

threading.Thread(target=keyboard_thread, daemon=True).start()

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
                "max_tokens": 1024,
                "response_format": {"type": "json_object"}
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
                
                # Check if there is an error in response
                has_error = False
                if isinstance(res_body, list) and len(res_body) > 0 and "error" in res_body[0]:
                    has_error = True
                    error_msg = res_body[0]["error"]["message"]
                    code = res_body[0]["error"]["code"]
                elif isinstance(res_body, dict) and "error" in res_body:
                    has_error = True
                    error_msg = res_body["error"]["message"]
                    code = res_body["error"]["code"]
                    
                if has_error:
                    print(f"\n[大腦回傳錯誤]: {code} - {error_msg}")
                    break
                    
                response_text = res_body["choices"][0]["message"]["content"]
                
                # Filter out <thought>...</thought> tags to ensure valid JSON
                import re
                response_text = re.sub(r"<thought>.*?</thought>", "", response_text, flags=re.DOTALL).strip()
                # Clean up markdown code blocks if present
                if response_text.startswith("```json"):
                    response_text = re.sub(r"^```json\s*", "", response_text)
                    response_text = re.sub(r"\s*```$", "", response_text)
                
                try:
                    agent_response = json.loads(response_text)
                except json.JSONDecodeError:
                    # Fallback if not JSON
                    agent_response = {"message": response_text, "tool_name": None}
                
                thought = agent_response.get("thought", "")
                tool_name = agent_response.get("tool_name", "")
                tool_args = agent_response.get("tool_args", "")
                message_text = agent_response.get("message", "")
                
                messages.append({"role": "assistant", "content": response_text})
                
                if tool_name and str(tool_name).strip() and str(tool_name).lower() != "null":
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
                        messages.append({"role": "system", "content": f"工具 {tool_name} 的執行結果:\n{tool_result}"})
                    
                    continue
                
                # No tool call, process the message
                if message_text:
                    print(f"\r\033[K小派: {message_text}", flush=True)
                    oled.draw_screen(current_text=message_text)
                    
                    # 語音合成輸出
                    if tts and str(message_text).strip():
                        try:
                            speak_text = str(message_text).replace("AI", "欸哀")
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
                else:
                    print(f"\n[系統] 模型未回傳有效訊息。原始回傳內容: {response_text}")
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
