import time
import os
import sys
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from PIL import Image, ImageDraw, ImageFont
from gpiozero import Button

# 強制使用 lgpio
os.environ['GPIOZERO_PIN_FACTORY'] = 'lgpio'

# 初始化 OLED
try:
    serial = i2c(port=1, address=0x3C)
    device = ssd1306(serial)
    font = ImageFont.truetype("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 14)
except Exception as e:
    sys.exit(1)

options = [
    "1. API 雲端 (純文字)",
    "2. 本地大腦 (純文字)",
    "3. API 雲端 (語音)",
    "4. 本地大腦 (語音)",
    "5. 關閉選單"
]

current_idx = 0
click_count = 0
last_click_time = 0

def draw_menu():
    image = Image.new("1", (device.width, device.height))
    draw = ImageDraw.Draw(image)
    draw.text((0, 0), "--- 小派啟動選單 ---", font=font, fill=255)
    text = options[current_idx]
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text(((device.width - w) // 2, 28), text, font=font, fill=255)
    draw.text((0, 50), "單擊:換項  雙擊:啟動", font=font, fill=255)
    device.display(image)

def next_item():
    global current_idx
    current_idx = (current_idx + 1) % len(options)
    draw_menu()

def confirm():
    # 輸出結果並徹底退出
    print(current_idx + 1)
    sys.stdout.flush()
    os._exit(0)

def on_pressed():
    global click_count, last_click_time
    click_count += 1
    last_click_time = time.time()

# 初始化按鈕
btn = Button(22, pull_up=True, bounce_time=0.05)
btn.when_pressed = on_pressed

draw_menu()

# 主迴圈監控點擊次數
try:
    while True:
        if click_count > 0:
            # 等待 0.35 秒看是否有連擊
            time.sleep(0.35)
            if click_count == 1:
                next_item()
            else:
                confirm()
            click_count = 0 # 重置計數
        time.sleep(0.05)
except KeyboardInterrupt:
    sys.exit(1)
