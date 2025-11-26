import streamlit as st
import requests
import time
import pytz
import base64
import concurrent.futures
from datetime import datetime
from openai import OpenAI

# ================== 🔒 安全設定區 ==================
try:
    DUOPLUS_API_KEY = st.secrets["DUOPLUS_API_KEY"]
    BASE_URL = "https://openapi.duoplus.net"
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
except:
    st.error("⚠️ API Key 未設定，請在 Streamlit Secrets 設定。")
    st.stop()

# 📡 Colab 狀態信箱
COLAB_STATUS_URL = "https://jsonblob.com/api/jsonBlob/019abe39-7045-7d9d-baa4-ef73f78f2a8e"

# 設備清單
DEVICES = {
    "👑 MyWA (老闆)": {"id": "1ZxjQ", "phone": "886916802803"},
    "💄 Aiko (美妝)": {"id": "F8Z5z", "phone": "6281299393526"},
    "🎮 Jiarong (電玩)": {"id": "TkRrq", "phone": "6282277721042"},
    "👶 Hiro (新人)": {"id": "6aY1w", "phone": "6282342432368"}
}

DEFAULT_PERSONAS = {
    "1ZxjQ": "You are MyWA, the boss. Brief, professional but casual.",
    "F8Z5z": "You are Aiko. Love beauty & fashion. Use emojis.",
    "TkRrq": "You are Jiarong. Gamer, love Steam & PS5. Speak like a bro.",
    "6aY1w": "You are Hiro. Newbie, polite, curious."
}

client = OpenAI(api_key=OPENAI_API_KEY)

# ================== 🔧 後端函數 ==================

def get_colab_status():
    try:
        res = requests.get(COLAB_STATUS_URL, timeout=3)
        return res.json()
    except:
        return None

def send_adb(image_id, cmd):
    """發送 ADB 指令並回傳結果"""
    url = f"{BASE_URL}/api/v1/cloudPhone/command"
    headers = {"DuoPlus-API-Key": DUOPLUS_API_KEY, "Content-Type": "application/json"}
    payload = {"image_ids": [image_id], "command": cmd}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        return res.json()
    except Exception as e:
        return {"code": 500, "message": str(e)}

def get_screenshot(image_id):
    """📸 獲取單台畫面 (回傳 binary 或 None)"""
    cmd = "screencap -p | base64 -w 0"
    res = send_adb(image_id, cmd)
    try:
        if res.get('code') == 200:
            raw_output = res.get('data', {}).get(image_id, "")
            # 簡單驗證是否為 Base64
            if len(raw_output) > 100:
                return base64.b64decode(raw_output)
    except:
        pass
    return None

def fetch_all_screenshots_parallel():
    """⚡ 加速：同時抓取所有設備截圖"""
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        # 建立任務清單
        future_to_id = {executor.submit(get_screenshot, info['id']): dev_id for dev_id, info in DEVICES.items()}
        for future in concurrent.futures.as_completed(future_to_id):
            dev_name = future_to_id[future] # 其實這裡是 key name
            # 找出對應的 ID
            target_id = None
            for name, info in DEVICES.items():
                if info['id'] == future_to_id[future]: # wait logic slightly wrong above, fix below
                    pass 
            
            try:
                data = future.result()
                if data:
                    results[future_to_id[future]] = data # Key 是 device_id
            except:
                pass
    return results

def power_on_device(device_id):
    url = f"{BASE_URL}/api/v1/device/open"
    headers = {"DuoPlus-API-Key": DUOPLUS_API_KEY, "Content-Type": "application/json"}
    payload = {"device_id": device_id}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        return res.json()
    except Exception as e:
        return {"code": 500, "message": str(e)}

def check_online_status(image_id):
    res = send_adb(image_id, "ls")
    if res.get('code') == 200:
        return True
    return False

# ================== 🖥️ 前端頁面 ==================

st.set_page_config(page_title="DuoPlus 戰情中心", layout="wide", page_icon="📱")

# --- 側邊欄 ---
with st.sidebar:
    st.title("🎛️ 中控面板")
    
    # === 🔥 新增：自動監控開關 ===
    st.markdown("### 📸 自動監控")
    auto_refresh_mode = st.toggle("啟動每 30 秒自動截圖", value=False)
    
    if st.button("🔄 手動刷新狀態", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 📡 Colab 訊號")
    colab_data = get_colab_status()
    if colab_data:
        msg = colab_data.get("message", "無訊號")
        last_time = colab_data.get("last_update", "")
        st.info(f"**{msg}**")
        st.caption(f"Update: {last_time}")
        if last_time: st.success("連線正常 ✅")
    else:
        st.error("無法連接信箱 ❌")

# --- 主畫面 ---
st.title("🤖 DuoPlus 雲手機戰情中心 v3.4")
st.caption("Mode: Hybrid Cloud | Auto-Monitor: " + ("ON" if auto_refresh_mode else "OFF"))

# 如果開啟自動模式，嘗試並行抓圖
if auto_refresh_mode:
    # 這裡只在每次 rerun 時執行一次
    # 為了避免每次操作按鈕都重抓，我們可以只在倒數結束時抓
    # 但 Streamlit 機制比較特殊，我們直接抓最新的放入 Session
    
    # 使用 Spinner 顯示進度
    with st.spinner("⚡ 正在同步所有畫面..."):
        # 平行處理抓圖 (速度快)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_map = {executor.submit(get_screenshot, info['id']): info['id'] for name, info in DEVICES.items()}
            for future in concurrent.futures.as_completed(future_map):
                d_id = future_map[future]
                img = future.result()
                if img:
                    st.session_state[f"img_{d_id}"] = img

tab_monitor, tab_ai = st.tabs(["👁️ 實時監控", "🧠 AI 設定"])

with tab_monitor:
    cols = st.columns(4)
    for i, (name, info) in enumerate(DEVICES.items()):
        dev_id = info['id']
        with cols[i]:
            with st.container(border=True):
                st.subheader(name.split(" ")[0])
                st.caption(f"ID: {dev_id}")
                
                # 顯示圖片 (如果有在 Session 中)
                img_key = f"img_{dev_id}"
                if img_key in st.session_state:
                    st.image(st.session_state[img_key], caption="最新畫面", use_container_width=True)
                else:
                    st.info("尚無畫面 (請開啟自動監控或手動截圖)")

                # 操作按鈕
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("📸", key=f"s_{dev_id}", help="單張截圖"):
                        img = get_screenshot(dev_id)
                        if img: st.session_state[img_key] = img
                        st.rerun()
                with c2:
                    if st.button("🏠", key=f"h_{dev_id}", help="回首頁"):
                        send_adb(dev_id, "input keyevent 3")
                        st.toast("已按 Home")
                with c3:
                    if st.button("💬", key=f"w_{dev_id}", help="開 WhatsApp"):
                        send_adb(dev_id, 'am start -a android.intent.action.VIEW -d "https://wa.me/" com.whatsapp')
                        st.toast("開啟 WhatsApp")

with tab_ai:
    if 'personas' not in st.session_state:
        st.session_state['personas'] = DEFAULT_PERSONAS.copy()
    for name, info in DEVICES.items():
        with st.expander(f"設定 {name}"):
            st.session_state['personas'][info['id']] = st.text_area(f"Prompt", st.session_state['personas'][info['id']], height=70)

st.divider()
tz = pytz.timezone('Asia/Taipei')
now_str = datetime.now(tz).strftime('%H:%M:%S')
st.caption(f"Server Time: {now_str}")

# === 🔥 自動刷新邏輯 ===
if auto_refresh_mode:
    # 顯示倒數計時條
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 倒數 30 秒
    for i in range(30):
        # 為了讓使用者還有機會按「停止」，我們切成 30 次 1 秒
        time.sleep(1)
        progress = (i + 1) / 30
        progress_bar.progress(progress)
        status_text.text(f"下一次更新: {30 - i} 秒後...")
    
    # 時間到，重新整理網頁
    st.rerun()
