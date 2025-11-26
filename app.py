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
    cmd = "dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'"
    res = send_adb(image_id, cmd)
    if res.get('code') == 200:
        output = res.get('data', {}).get(image_id, "")
        if "com.whatsapp" in output: return "💬 WhatsApp"
        elif "launcher" in output: return "🏠 桌面"
        elif "SystemUI" in output: return "🔒 鎖定"
    return "未知 App"

def get_screen_text_smart(image_id):
    """🧠 聰明讀字：在手機端過濾，只回傳對話"""
    # 1. 產生 XML
    send_adb(image_id, "uiautomator dump /data/local/tmp/ui.xml")
    
    # 2. 關鍵修改：直接在手機用 grep 過濾出含有 text="..." 的行
    # 這樣回傳的資料量只有原本的 1%，絕對不會被 API 卡掉
    cmd_read = "grep 'text=\"' /data/local/tmp/ui.xml"
    res = send_adb(image_id, cmd_read)
    
    found_texts = []
    if res.get('code') == 200:
        raw_data = res.get('data', {}).get(image_id, "")
        # 解析 grep 出來的行
        matches = re.findall(r'text="([^"]+)"', raw_data)
        for m in matches:
            # 過濾掉時間、電量、WhatsApp 介面文字
            if len(m) > 2 and m not in ["WhatsApp", "Type a message", "Message", "Voice call", "Video call"]:
                found_texts.append(m)
    
    # 只回傳最後 6 句 (通常是最新對話)
    if found_texts:
        return found_texts[-6:]
    return ["(無新訊息)"]

def power_on_device(device_id):
    url = f"{BASE_URL}/api/v1/device/open"
    headers = {"DuoPlus-API-Key": DUOPLUS_API_KEY, "Content-Type": "application/json"}
    payload = {"device_id": device_id}
    try:
        requests.post(url, headers=headers, json=payload, timeout=5)
    except:
        pass

def check_online_status(image_id):
    res = send_adb(image_id, "ls")
    if res.get('code') == 200: return True
    return False

# ================== 🖥️ 前端頁面 ==================

st.set_page_config(page_title="DuoPlus 戰情中心", layout="wide", page_icon="📱")

# --- 側邊欄 ---
with st.sidebar:
    st.title("🎛️ 中控面板")
    
    if st.button("🔄 全機刷新"):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("### 📡 Colab 訊號")
    colab_data = get_colab_status()
    if colab_data:
        msg = colab_data.get("message", "無訊號")
        last_time = colab_data.get("last_update", "")
        st.info(f"**{msg}**")
        st.caption(f"Update: {last_time}")
        if last_time: st.success("運作正常 ✅")
    else:
        st.error("Colab 失聯 ❌")

# --- 主畫面 ---
st.title("🤖 DuoPlus 雲手機戰情中心 v3.7")
st.caption("Mode: Smart Text Reader | Connection: Stable")

tab_monitor, tab_ai = st.tabs(["👁️ 實時監控", "🧠 AI 設定"])

with tab_monitor:
    st.info("💡 點擊「📝 讀取對話」可查看最新聊天記錄。")

    # 並行偵測 App 狀態 (加速)
    app_states = {}
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
                
                is_online = check_online_status(dev_id)
                if is_online:
                    st.success(f"🟢 {app_states.get(dev_id, 'Checking...')}")
                    
                    # === 📝 讀取對話功能 ===
                    if st.button("📝 讀取對話", key=f"read_{dev_id}", use_container_width=True):
                        with st.spinner("解析畫面文字..."):
                            texts = get_screen_text_smart(dev_id)
                            st.session_state[f"txt_{dev_id}"] = texts
                    
                    # 顯示對話框
                    chat_logs = st.session_state.get(f"txt_{dev_id}", [])
                    if chat_logs:
                        with st.expander("💬 最新內容", expanded=True):
                            for t in chat_logs:
                                st.text(f"• {t}")
                    else:
                        st.caption("尚無資料")
                    # ====================

                    st.markdown("---")
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
                    if st.button("⚡ 開機", key=f"pwr_{dev_id}"):
                        power_on_device(dev_id)
                        st.info("指令已發送")
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
