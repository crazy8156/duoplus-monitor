import streamlit as st
import requests
import time
import pytz
from datetime import datetime
from openai import OpenAI

# ================== 🔒 安全設定區 ==================
try:
    DUOPLUS_API_KEY = st.secrets["DUOPLUS_API_KEY"]
    BASE_URL = "https://openapi.duoplus.net"
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
except:
    st.error("⚠️ 尚未設定 API Key！請在 Streamlit 後台設定 Secrets。")
    st.stop()

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

def send_adb(image_id, cmd):
    """發送 ADB 指令"""
    url = f"{BASE_URL}/api/v1/cloudPhone/command"
    headers = {"DuoPlus-API-Key": DUOPLUS_API_KEY, "Content-Type": "application/json"}
    payload = {"image_ids": [image_id], "command": cmd}
    try:
        requests.post(url, headers=headers, json=payload, timeout=5)
    except:
        pass

def power_on_device(device_id):
    """🔥 發送開機指令"""
    url = f"{BASE_URL}/api/v1/device/open"
    headers = {"DuoPlus-API-Key": DUOPLUS_API_KEY, "Content-Type": "application/json"}
    payload = {"device_id": device_id}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        return res.json()
    except Exception as e:
        return {"code": 500, "message": str(e)}

def check_online_status(image_id):
    """檢查 ADB 是否連線"""
    url = f"{BASE_URL}/api/v1/cloudPhone/command"
    headers = {"DuoPlus-API-Key": DUOPLUS_API_KEY, "Content-Type": "application/json"}
    try:
        res = requests.post(url, headers=headers, json={"image_ids": [image_id], "command": "ls"}, timeout=3)
        if res.status_code == 200 and res.json().get('code') == 200:
            return True
        return False
    except:
        return False

# ================== 🖥️ 前端頁面 (Streamlit) ==================

st.set_page_config(page_title="DuoPlus 戰情中心", layout="wide", page_icon="📱")

with st.sidebar:
    st.title("🎛️ 中控面板")
    if st.button("🔄 刷新全機狀態", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("### 廣播系統")
    broadcast_txt = st.text_input("輸入文字 (英文)", placeholder="Hello Team...")
    if st.button("📢 發送給所有人"):
        if broadcast_txt:
            progress = st.progress(0)
            active_count = 0
            for idx, (name, info) in enumerate(DEVICES.items()):
                if check_online_status(info['id']):
                    send_adb(info['id'], f"input text {broadcast_txt.replace(' ', '%s')}")
                    send_adb(info['id'], "input keyevent 66") 
                    active_count += 1
                progress.progress((idx + 1) / len(DEVICES))
            
            if active_count < len(DEVICES):
                st.warning(f"廣播已發送，但只有 {active_count} 台在線。")
            else:
                st.success("廣播已成功發送給所有設備！")

st.title("🤖 DuoPlus 雲手機戰情中心 v3.1")
st.caption("Cloud Mode: Online | Connection: Secure")

tab_monitor, tab_ai = st.tabs(["👁️ 實時監控", "🧠 AI 設定"])

with tab_monitor:
    st.info("💡 若設備離線，請點擊「⚡ 立即開機」並等待約 1-2 分鐘。")
    cols = st.columns(4)
    for i, (name, info) in enumerate(DEVICES.items()):
        dev_id = info['id']
        with cols[i]:
            with st.container(border=True):
                st.subheader(name.split(" ")[0])
                st.caption(f"ID: {dev_id}")
                
                # 狀態檢查
                is_online = check_online_status(dev_id)
                
                if is_online:
                    st.success("🟢 在線")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🏠 Home", key=f"h_{dev_id}"):
                            send_adb(dev_id, "input keyevent 3")
                            st.toast("已按 Home")
                    with c2:
                        # 這是您剛剛報錯的地方，請確認這裡是否完整
                        if st.button("💬 App", key=f"w_{dev_id}"):
                            cmd = 'am start -a android.intent.action.VIEW -d "https://wa.me/" com.whatsapp'
                            send_adb(dev_id, cmd)
                            st.toast("開啟 WhatsApp")
                else:
                    st.error("🔴 離線")
                    if st.button("⚡ 立即開機", key=f"pwr_{dev_id}", type="primary"):
                        with st.spinner("發送指令中..."):
                            res = power_on_device(dev_id)
                            if res.get('code') == 200:
                                st.success("已發送！請稍候...")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(f"失敗: {res.get('message')}")

with tab_ai:
    st.info("在此修改人設")
    if 'personas' not in st.session_state:
        st.session_state['personas'] = DEFAULT_PERSONAS.copy()
    
    for name, info in DEVICES.items():
        with st.expander(f"設定 {name}"):
            st.session_state['personas'][info['id']] = st.text_area(f"Prompt", st.session_state['personas'][info['id']], height=70)

st.divider()
tz = pytz.timezone('Asia/Taipei')
st.caption(f"Server Time: {datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')} (Taipei)")
