import streamlit as st
import requests
import time
import pytz
import re
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
        res = requests.post(url, headers=headers, json=payload, timeout=8)
        return res.json()
    except Exception as e:
        return {"code": 500, "message": str(e)}

def get_current_app(image_id):
    """🕵️ 偵測目前前台 App"""
    # 使用 dumpsys 查詢目前的 Focus
    cmd = "dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'"
    res = send_adb(image_id, cmd)
    
    if res.get('code') == 200:
        output = res.get('data', {}).get(image_id, "")
        if "com.whatsapp" in output:
            return "💬 WhatsApp"
        elif "launcher" in output:
            return "🏠 桌面 (Home)"
        elif "SystemUI" in output:
            return "🔒 鎖定/系統"
        elif output:
            return f"❓ 未知 ({output[:20]}...)"
    return "Unknown"

def get_screen_text(image_id):
    """📝 讀取螢幕上的文字 (XML dump)"""
    # 1. Dump UI 結構
    send_adb(image_id, "uiautomator dump /data/local/tmp/ui.xml")
    # 2. 讀取檔案
    res = send_adb(image_id, "cat /data/local/tmp/ui.xml")
    
    found_texts = []
    if res.get('code') == 200:
        xml_data = res.get('data', {}).get(image_id, "")
        # 簡單 Regex 提取 text="..."
        matches = re.findall(r'text="([^"]+)"', xml_data)
        for m in matches:
            if m.strip(): # 過濾空字串
                found_texts.append(m)
    
    # 過濾掉系統雜訊，只留最後 5 句
    if found_texts:
        return found_texts[-5:] 
    return ["(無可讀文字)"]

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
    
    st.markdown("### 📡 監控模式")
    # 開關：是否要開啟 App 偵測 (會稍微變慢)
    enable_app_check = st.toggle("啟用 App 狀態偵測", value=True)
    
    if st.button("🔄 全機刷新"):
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
        if last_time: st.success("Colab 運作中 ✅")
    else:
        st.error("Colab 失聯 ❌")

# --- 主畫面 ---
st.title("🤖 DuoPlus 雲手機戰情中心 v3.6")
st.caption("Mode: Text X-Ray (Fast & Stable)")

tab_monitor, tab_ai = st.tabs(["👁️ 狀態透視", "🧠 AI 設定"])

with tab_monitor:
    st.info("由於 API 限制圖片傳輸，系統已切換為「文字透視模式」，可直接讀取 App 狀態與對話內容。")
    
    # 為了加速，若開啟 App 偵測，使用並行處理
    app_states = {}
    if enable_app_check:
        with st.spinner("正在掃描所有設備 App 狀態..."):
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                future_map = {executor.submit(get_current_app, info['id']): info['id'] for name, info in DEVICES.items()}
                for future in concurrent.futures.as_completed(future_map):
                    d_id = future_map[future]
                    app_states[d_id] = future.result()

    cols = st.columns(4)
    for i, (name, info) in enumerate(DEVICES.items()):
        dev_id = info['id']
        with cols[i]:
            with st.container(border=True):
                st.subheader(name.split(" ")[0])
                st.caption(f"ID: {dev_id}")
                
                # 1. 在線狀態
                is_online = check_online_status(dev_id)
                if is_online:
                    st.success("🟢 在線")
                    
                    # 2. 目前 App 狀態
                    if enable_app_check:
                        current_app = app_states.get(dev_id, "偵測中...")
                        st.metric("目前畫面", current_app)
                    
                    # 3. 螢幕讀字 (手動觸發)
                    with st.expander("📝 讀取螢幕文字"):
                        if st.button("讀取內容", key=f"read_{dev_id}"):
                            with st.spinner("分析中..."):
                                texts = get_screen_text(dev_id)
                                for t in texts:
                                    st.text(f"- {t}")
                                if not texts:
                                    st.caption("無可讀文字")

                    st.markdown("---")
                    # 操作按鈕
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🏠 Home", key=f"h_{dev_id}"):
                            send_adb(dev_id, "input keyevent 3")
                            st.toast("已按 Home")
                    with c2:
                        if st.button("💬 App", key=f"w_{dev_id}"):
                            send_adb(dev_id, 'am start -a android.intent.action.VIEW -d "https://wa.me/" com.whatsapp')
                            st.toast("開啟 WhatsApp")
                else:
                    st.error("🔴 離線")
                    if st.button("⚡ 開機", key=f"pwr_{dev_id}", type="primary"):
                        power_on_device(dev_id)
                        st.success("指令已發送")
                        time.sleep(2)
                        st.rerun()

with tab_ai:
    if 'personas' not in st.session_state:
        st.session_state['personas'] = DEFAULT_PERSONAS.copy()
    for name, info in DEVICES.items():
        with st.expander(f"設定 {name}"):
            st.session_state['personas'][info['id']] = st.text_area(f"Prompt", st.session_state['personas'][info['id']], height=70)

st.divider()
tz = pytz.timezone('Asia/Taipei')
st.caption(f"Server Time: {datetime.now(tz).strftime('%H:%M:%S')}")
