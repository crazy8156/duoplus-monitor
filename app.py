import streamlit as st
import requests
import time
import pytz
import re
import pandas as pd
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

client = OpenAI(api_key=OPENAI_API_KEY)

# ================== 📂 設備載入系統 (CSV) ==================

@st.cache_data
def load_devices_from_csv():
    """從 GitHub 或本地讀取 devices.csv"""
    try:
        # 嘗試讀取同目錄下的 devices.csv
        df = pd.read_csv("devices.csv")
        
        # 清理欄位名稱 (去除空白)
        df.columns = [c.strip() for c in df.columns]
        
        devices = {}
        # 轉換為字典格式
        for index, row in df.iterrows():
            # 確保必要的欄位存在 (ID, 名稱, 備註/電話)
            # 根據你的 CSV 截圖，ID是 'ID', 名稱是 '名稱', 電話可能在 '備註' 或你需要手動填
            # 這裡做一個防呆：如果沒有電話欄位，就標記 'No Phone'
            
            d_id = str(row.get('ID', '')).strip()
            name = str(row.get('名稱', f'Device_{index}')).strip()
            
            # 嘗試找電話號碼 (通常在備註，或你需要新增一欄 'Phone')
            # 這裡假設備註欄位就是電話，如果不是，你可能需要整理一下 CSV
            remark = str(row.get('備註', '')).strip()
            phone = remark if remark.startswith('62') or remark.startswith('886') else "Unknown"
            
            if d_id:
                devices[name] = {"id": d_id, "phone": phone}
        
        return devices
    except Exception as e:
        st.error(f"無法讀取 CSV: {e}")
        # 回退到預設 4 台
        return {
            "👑 MyWA (老闆)": {"id": "1ZxjQ", "phone": "886916802803"},
            "💄 Aiko (美妝)": {"id": "F8Z5z", "phone": "6281299393526"},
            "🎮 Jiarong (電玩)": {"id": "TkRrq", "phone": "6282277721042"},
            "👶 Hiro (新人)": {"id": "6aY1w", "phone": "6282342432368"}
        }

DEVICES = load_devices_from_csv()

# 自動生成預設人設 (如果沒有設定過)
DEFAULT_PERSONAS = {}
for name in DEVICES.keys():
    DEFAULT_PERSONAS[DEVICES[name]['id']] = "You are a casual user using WhatsApp. Friendly and polite."

# ================== 🔧 後端函數 ==================

def get_colab_status():
    try:
        res = requests.get(COLAB_STATUS_URL, timeout=3)
        return res.json()
    except:
        return None

def send_adb(image_id, cmd):
    url = f"{BASE_URL}/api/v1/cloudPhone/command"
    headers = {"DuoPlus-API-Key": DUOPLUS_API_KEY, "Content-Type": "application/json"}
    payload = {"image_ids": [image_id], "command": cmd}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=8)
        return res.json()
    except:
        return {"code": 500}

def get_current_app(image_id):
    """偵測 App"""
    cmd = "dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'"
    res = send_adb(image_id, cmd)
    if res.get('code') == 200:
        output = res.get('data', {}).get(image_id, "")
        if "com.whatsapp" in output: return "💬 WhatsApp"
        elif "launcher" in output: return "🏠 桌面"
        elif "SystemUI" in output: return "🔒 鎖定"
    return "未知"

def get_screen_text_smart(image_id):
    """讀取對話"""
    send_adb(image_id, "uiautomator dump /data/local/tmp/ui.xml")
    cmd_read = "grep 'text=\"' /data/local/tmp/ui.xml"
    res = send_adb(image_id, cmd_read)
    
    found_texts = []
    if res.get('code') == 200:
        raw_data = res.get('data', {}).get(image_id, "")
        matches = re.findall(r'text="([^"]+)"', raw_data)
        for m in matches:
            if len(m) > 2 and m not in ["WhatsApp", "Type a message", "Message", "Voice call"]:
                found_texts.append(m)
    if found_texts: return found_texts[-6:]
    return ["(無新訊息)"]

def power_on_device(device_id):
    url = f"{BASE_URL}/api/v1/device/open"
    headers = {"DuoPlus-API-Key": DUOPLUS_API_KEY, "Content-Type": "application/json"}
    payload = {"device_id": device_id}
    requests.post(url, headers=headers, json=payload, timeout=5)

def check_online_status(image_id):
    res = send_adb(image_id, "ls")
    return True if res.get('code') == 200 else False

# ================== 🖥️ 前端頁面 ==================

st.set_page_config(page_title="DuoPlus 戰情中心", layout="wide", page_icon="📱")

with st.sidebar:
    st.title("🎛️ 中控面板")
    st.info(f"目前監控設備數: {len(DEVICES)} 台")
    
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
        if last_time: st.success("運作正常 ✅")
    else:
        st.error("Colab 失聯 ❌")

st.title("🤖 DuoPlus 雲手機戰情中心 v4.0")
st.caption("Mode: Mass Control | Source: CSV")

# 分頁控制 (每頁顯示 8 台，避免網頁卡頓)
DEVICES_PER_PAGE = 8
device_list = list(DEVICES.items())
total_pages = (len(device_list) - 1) // DEVICES_PER_PAGE + 1

if total_pages > 1:
    page = st.slider("選擇頁數", 1, total_pages, 1)
else:
    page = 1

start_idx = (page - 1) * DEVICES_PER_PAGE
end_idx = min(start_idx + DEVICES_PER_PAGE, len(device_list))
current_page_devices = device_list[start_idx:end_idx]

tab_monitor, tab_ai = st.tabs(["👁️ 實時監控", "🧠 AI 設定"])

with tab_monitor:
    st.markdown(f"### 顯示第 {start_idx+1} - {end_idx} 台 (共 {len(DEVICES)} 台)")
    
    # 智慧並行偵測 (只偵測當前頁面)
    app_states = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_map = {executor.submit(get_current_app, info['id']): info['id'] for name, info in current_page_devices}
        for future in concurrent.futures.as_completed(future_map):
            d_id = future_map[future]
            app_states[d_id] = future.result()

    cols = st.columns(4) # 4欄佈局
    
    for i, (name, info) in enumerate(current_page_devices):
        dev_id = info['id']
        col_idx = i % 4
        
        with cols[col_idx]:
            with st.container(border=True):
                st.subheader(name)
                st.caption(f"ID: {dev_id}")
                
                is_online = check_online_status(dev_id)
                if is_online:
                    st.success(f"🟢 {app_states.get(dev_id, 'Checking...')}")
                    
                    if st.button("📝 讀取對話", key=f"read_{dev_id}", use_container_width=True):
                        with st.spinner("讀取中..."):
                            texts = get_screen_text_smart(dev_id)
                            st.session_state[f"txt_{dev_id}"] = texts
                    
                    chat_logs = st.session_state.get(f"txt_{dev_id}", [])
                    if chat_logs:
                        with st.expander("內容", expanded=True):
                            for t in chat_logs: st.text(f"• {t}")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🏠", key=f"h_{dev_id}"):
                            send_adb(dev_id, "input keyevent 3")
                            st.toast("已按 Home")
                    with c2:
                        if st.button("💬", key=f"w_{dev_id}"):
                            send_adb(dev_id, 'am start -a android.intent.action.VIEW -d "https://wa.me/" com.whatsapp')
                            st.toast("開啟 WA")
                else:
                    st.error("🔴 離線")
                    if st.button("⚡ 開機", key=f"pwr_{dev_id}", type="primary"):
                        power_on_device(dev_id)
                        st.info("指令發送")
                        time.sleep(2)
                        st.rerun()

with tab_ai:
    if 'personas' not in st.session_state:
        st.session_state['personas'] = DEFAULT_PERSONAS.copy()
    
    st.info("這裡可以為每一台設備設定獨特的人設")
    for name, info in current_page_devices:
        d_id = info['id']
        if d_id not in st.session_state['personas']:
            st.session_state['personas'][d_id] = "Casual user."
        
        with st.expander(f"設定 {name}"):
            st.session_state['personas'][d_id] = st.text_area(f"Prompt", st.session_state['personas'][d_id], height=70, key=f"ai_{d_id}")

st.divider()
tz = pytz.timezone('Asia/Taipei')
st.caption(f"Server Time: {datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')}")
