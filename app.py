import streamlit as st
import requests
import time
import pytz
from datetime import datetime
from openai import OpenAI

# ================== 🔒 安全設定區 ==================
# 這些 Key 會從 Streamlit 的 Secrets 讀取，確保安全
try:
    DUOPLUS_API_KEY = st.secrets["DUOPLUS_API_KEY"]
    BASE_URL = "https://openapi.duoplus.net"
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
except:
    st.error("⚠️ 尚未設定 API Key！請在 Streamlit 後台設定 Secrets。")
    st.stop()

# 設備清單 (v1.6.0 黃金確認版)
DEVICES = {
    "👑 MyWA (老闆)": {"id": "1ZxjQ", "phone": "886916802803"},
    "💄 Aiko (美妝)": {"id": "F8Z5z", "phone": "6281299393526"},
    "🎮 Jiarong (電玩)": {"id": "TkRrq", "phone": "6282277721042"},
    "👶 Hiro (新人)": {"id": "6aY1w", "phone": "6282342432368"}
}

# 預設人設
DEFAULT_PERSONAS = {
    "1ZxjQ": "You are MyWA, the boss. Brief, professional but casual.",
    "F8Z5z": "You are Aiko. Love beauty & fashion. Use emojis.",
    "TkRrq": "You are Jiarong. Gamer, love Steam & PS5. Speak like a bro.",
    "6aY1w": "You are Hiro. Newbie, polite, curious."
}

# 初始化 OpenAI
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

def check_online_status(image_id):
    """檢查是否在線"""
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

# 側邊欄
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
            for idx, (name, info) in enumerate(DEVICES.items()):
                send_adb(info['id'], f"input text {broadcast_txt.replace(' ', '%s')}")
                send_adb(info['id'], "input keyevent 66") 
                progress.progress((idx + 1) / len(DEVICES))
            st.success("廣播已發送！")

# 主頁面
st.title("🤖 DuoPlus 雲手機戰情中心")
st.caption("Cloud Mode: Online | Connection: Secure")

tab_monitor, tab_ai = st.tabs(["👁️ 實時監控", "🧠 AI 設定"])

with tab_monitor:
    st.info("💡 提示：點擊「🏠 Home」可強制回桌面，點擊「💬 App」可強制重啟 WhatsApp。")
    cols = st.columns(4)
    for i, (name, info) in enumerate(DEVICES.items()):
        dev_id = info['id']
        with cols[i]:
            with st.container(border=True):
                st.subheader(name.split(" ")[0])
                st.caption(f"ID: {dev_id}")
                
                # 檢查狀態
                if check_online_status(dev_id):
                    st.success("🟢 在線")
                else:
                    st.error("🔴 離線")
                
                # 操作按鈕
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🏠 Home", key=f"h_{dev_id}"):
                        send_adb(dev_id, "input keyevent 3")
                        st.toast("已按 Home")
                with c2:
                    if st.button("💬 App", key=f"w_{dev_id}"):
                        cmd = 'am start -a android.intent.action.VIEW -d "https://wa.me/" com.whatsapp'
                        send_adb(dev_id, cmd)
                        st.toast("開啟 WhatsApp")

with tab_ai:
    st.info("在此修改人設 (僅本次連線有效，長期修改請更新 GitHub 代碼)")
    if 'personas' not in st.session_state:
        st.session_state['personas'] = DEFAULT_PERSONAS.copy()
    
    # 使用 Expander 讓介面整潔
    for name, info in DEVICES.items():
        with st.expander(f"設定 {name}"):
            st.session_state['personas'][info['id']] = st.text_area(f"Prompt", st.session_state['personas'][info['id']], height=70)

st.divider()
tz = pytz.timezone('Asia/Taipei')
st.caption(f"Server Time: {datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')} (Taipei)")