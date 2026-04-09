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

initial_messages = [
    {"role": "system", "content": "你是「小派」，一個運行在樹莓派 5 上的AI語音助手，擁有視覺與聽覺。你的大腦是 Gemma 模型。你的回答要非常簡潔口語化，因為你要用 TTS 講出來，字數盡量少於 30 字。使用繁體中文。"}
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
            rec_stream = sd.InputStream(samplerate=16000, channels=1, callback=record_audio_callback)
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
        if whisper_model and recording is not None and len(recording) > 16000 * 0.5:
            try:
                sf.write("/tmp/temp_record.wav", recording, 16000)
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
            
        # 判斷是否需要呼叫相機
        if "看" in user_input or "拍照" in user_input or "這" in user_input:
            base64_img = capture_image_base64()
            if base64_img:
                msg_content = [
                    {"type": "text", "text": user_input},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                ]
                messages.append({"role": "user", "content": msg_content})
            else:
                messages.append({"role": "user", "content": user_input})
        else:
            messages.append({"role": "user", "content": user_input})
            
        oled.history.append(("user", user_input))
        oled.draw_screen()
        
        data = json.dumps({
            "messages": messages,
            "stream": True,
            "temperature": 0.6,
            "max_tokens": 100
        }).encode("utf-8")
        
        req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=data, headers={"Content-Type": "application/json"})
        
        print("小派: ", end="", flush=True)
        response_text = ""
        
        try:
            with urllib.request.urlopen(req) as response:
                for line in response:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: ") and line != "data: [DONE]":
                        chunk = json.loads(line[6:])
                        if "choices" in chunk and len(chunk["choices"]) > 0:
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"] is not None:
                                content = delta["content"]
                                if first_token:
                                    print("小派:                ", end="\r", flush=True)
                                    print("小派: ", end="", flush=True)
                                    first_token = False
                                print(content, end="", flush=True)
                                response_text += content
                                if len(response_text) % 2 == 0:
                                    oled.draw_screen(current_text=response_text)
            
            oled.draw_screen(current_text=response_text)
            print()
            messages.append({"role": "assistant", "content": response_text})
            
            # 語音合成輸出
            if tts and response_text.strip():
                try:
                    audio = tts.generate(response_text)
                    if audio and len(audio.samples) > 0:
                        sd.default.device = None # 使用系統預設
                        sd.play(audio.samples, audio.sample_rate)
                        sd.wait()
                except Exception as e:
                    print("播放語音失敗:", e)
                    
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode("utf-8")
            print(f"\n[大腦回傳錯誤]: {e.code} - {error_msg}")
            if "image" in error_msg.lower() or e.code == 400:
                print("[系統提示] 模型可能尚未正確載入視覺投影檔 (mmproj)。")
                messages.pop()
        
    except KeyboardInterrupt:
        oled.show_message("小派休息囉！Zzz")
        break
    except Exception as e:
        print(f"\n錯誤: {e}")
        oled.show_message("連線到大腦失敗 :(")
