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
    st.error("⚠️ API Key 未設定")
    st.stop()

# ⚠️ 請填入第一步產生的信箱網址
COLAB_STATUS_URL = "https://jsonblob.com/api/jsonBlob/019abe39-7045-7d9d-baa4-ef73f78f2a8e"

# 設備清單
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

client = OpenAI(api_key=OPENAI_API_KEY)

# ================== 🔧 後端函數 ==================

def get_colab_status():
    """檢查 Colab 是否活著"""
    try:
        res = requests.get(COLAB_STATUS_URL, timeout=3)
        data = res.json()
        
        last_update_str = data.get("last_update", "")
        msg = data.get("message", "Unknown")
        
        # 計算時間差
        if last_update_str:
            tz = pytz.timezone('Asia/Taipei')
            last_time = datetime.strptime(last_update_str, "%Y-%m-%d %H:%M:%S")
            # 這裡簡單處理，假設 Colab 和 Streamlit 都在標準時間
            # 比較好的做法是用 timestamp，但為了簡單先這樣
            
            # 判斷是否超過 15 分鐘沒更新 (Colab 可能斷了)
            # 注意：這裡的時間比較可能會有時區問題，建議看文字即可
            return data
        return None
    except:
        return None

def send_adb(image_id, cmd):
    url = f"{BASE_URL}/api/v1/cloudPhone/command"
    headers = {"DuoPlus-API-Key": DUOPLUS_API_KEY, "Content-Type": "application/json"}
    payload = {"image_ids": [image_id], "command": cmd}
    try:
        requests.post(url, headers=headers, json=payload, timeout=5)
    except:
        pass

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
    url = f"{BASE_URL}/api/v1/cloudPhone/command"
    headers = {"DuoPlus-API-Key": DUOPLUS_API_KEY, "Content-Type": "application/json"}
    try:
        res = requests.post(url, headers=headers, json={"image_ids": [image_id], "command": "ls"}, timeout=3)
        if res.status_code == 200 and res.json().get('code') == 200:
            return True
        return False
    except:
        return False

# ================== 🖥️ 前端頁面 ==================

st.set_page_config(page_title="DuoPlus 戰情中心", layout="wide", page_icon="📱")

# --- 側邊欄 ---
with st.sidebar:
    st.title("🎛️ 中控面板")
    if st.button("🔄 刷新全機狀態", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    # === 新增：Colab 狀態監控區 ===
    st.markdown("---")
    st.markdown("### 🖥️ Colab 排程狀態")
    
    colab_data = get_colab_status()
    if colab_data:
        last_msg = colab_data.get("message", "無資料")
        last_time = colab_data.get("last_update", "未知")
        
        st.info(f"**狀態**: {last_msg}")
        st.caption(f"最後回報: {last_time}")
        
        # 簡單檢查字串長度確保不是空值
        if len(last_time) > 5:
             st.success("訊號接收正常 📡")
        else:
             st.warning("訊號等待中...")
    else:
        st.error("❌ 無法連接 Colab 信箱")
        st.caption("請確認 Colab 是否正在執行")
    
    st.markdown("---")
    
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
                st.warning(f"只有 {active_count} 台在線。")
            else:
                st.success("廣播成功！")

# --- 主畫面 ---
st.title("🤖 DuoPlus 雲手機戰情中心 v3.2")
st.caption("Cloud Mode: Online | Connection: Secure")

tab_monitor, tab_ai = st.tabs(["👁️ 實時監控", "🧠 AI 設定"])

with tab_monitor:
    cols = st.columns(4)
    for i, (name, info) in enumerate(DEVICES.items()):
        dev_id = info['id']
        with cols[i]:
            with st.container(border=True):
                st.subheader(name.split(" ")[0])
                st.caption(f"ID: {dev_id}")
                
                is_online = check_online_status(dev_id)
                if is_online:
                    st.success("🟢 在線")
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
                else:
                    st.error("🔴 離線")
                    if st.button("⚡ 立即開機", key=f"pwr_{dev_id}", type="primary"):
                        with st.spinner("發送開機指令..."):
                            res = power_on_device(dev_id)
                            if res.get('code') == 200:
                                st.success("已發送！")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(f"失敗: {res.get('message')}")

with tab_ai:
    if 'personas' not in st.session_state:
        st.session_state['personas'] = DEFAULT_PERSONAS.copy()
    for name, info in DEVICES.items():
        with st.expander(f"設定 {name}"):
            st.session_state['personas'][info['id']] = st.text_area(f"Prompt", st.session_state['personas'][info['id']], height=70)

st.divider()
tz = pytz.timezone('Asia/Taipei')
st.caption(f"Server Time: {datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')} (Taipei)")
