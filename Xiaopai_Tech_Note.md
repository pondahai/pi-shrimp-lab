# 🍓 樹莓派專案技術筆記：小派 (Xiaopai) AI 助手

## 1. 專案概述 (Project Overview)
*   **專案名稱：** 小派 (Xiaopai)
*   **運行硬體：** 樹莓派 5 (Raspberry Pi 5)
*   **主機位址：** `raspberry.local` (使用者: `pi`)
*   **核心目標：** 在樹莓派上運行一個輕量化、具備文字對話、OLED 顯示與語音回饋功能的本地 AI 語音/文字助手。

## 2. 系統架構與核心模組 (System Architecture)
*   **大腦引擎 (LLM Engine)：** 
    *   **軟體：** `llama.cpp` (`llama-server`)
    *   **模型：** Gemma 輕量化模型 (`gemma-4-E2B-it-UD-IQ2_M.gguf`，2-bit 量化)
    *   **服務端點：** 本地端 `http://127.0.0.1:8080/v1/chat/completions`
    *   **設定參數：** Context Size 2048, 系統提示詞設定為繁體中文、友善、簡潔的在地化人格。
*   **主控程式 (Chat Interface)：** 
    *   **程式檔：** `xiaopai_chat.py` (執行於虛擬環境 `~/xiaopai_env/bin/python`)
    *   **功能：** 負責接收輸入、向本地 API 發送請求、並協調 OLED 顯示與語音輸出。
*   **硬體周邊控制：**
    *   **OLED 螢幕：** 發送請求時顯示「(思考中...)」動畫，並動態逐字渲染 AI 的回應。
    *   **語音輸出 (Audio)：** 接收音效檔案並透過 `sounddevice` 播放，強制指定系統預設音效卡 (`sd.default.device = None`) 以解決資源佔用與衝突問題。

## 3. PC 端遠端控制與互動 (Remote Interaction)
為方便在 PC 端直接操作與監控，開發了專屬的 Python 遠端控制腳本：
*   **`run_xiaopai_interactive.py`**
    *   使用 `paramiko` 建立 SSH 連線。
    *   開啟 PTY 互動式通道 (Interactive Session) 並執行 `start_xiaopai.sh`。
    *   透過多執行緒 (`threading`) 實時監聽遠端標準輸出，實現「打字機效果」的對話體驗。
    *   直接於本地終端機輸入文字，即可透過 SSH 傳送至樹莓派的小派程式。

## 4. 關鍵維護與除錯指令 (Maintenance & Debugging)
*   **檢查運行中的進程：** `ps aux | grep -iE 'llama-server|xiaopai_chat' | grep -v grep`
*   **檢查大腦引擎日誌：** `tail -n 20 ~/llama_server.log`
*   **檢查系統記憶體狀態：** `free -m`
*   **重啟/強制關閉對話介面：** `pkill -f 'python.*xiaopai_chat.py'`
*   **本地除錯腳本：** 
    *   `debug_xiaopai.py`：一鍵遠端執行上述檢查指令。
    *   `patch_xiaopai_final.py`：用於熱更新樹莓派上的程式碼（如：修正音效卡衝突、加入思考動畫）。

---
*筆記產生時間：2026年4月9日*
