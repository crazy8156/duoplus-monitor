import streamlit as st
import requests
import time
import pytz
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
    """讀取 CSV，失敗則回傳預設 4 台"""
    try:
        df = pd.read_csv("devices.csv")
        df.columns = [c.strip() for c in df.columns]
        devices = {}
        for index, row in df.iterrows():
            d_id = str(row.get('ID', '')).strip()
            name = str(row.get('名稱', f'Device_{index}')).strip()
            remark = str(row.get('備註', '')).strip()
            phone = remark if remark.startswith('62') or remark.startswith('886') else "Unknown"
            if d_id:
                devices[name] = {"id": d_id, "phone": phone}
        return devices
    except:
        # 預設名單
        return {
            "👑 MyWA (老闆)": {"id": "1ZxjQ", "phone": "886916802803"},
            "💄 Aiko (美妝)": {"id": "F8Z5z", "phone": "6281299393526"},
            "🎮 Jiarong (電玩)": {"id": "TkRrq", "phone": "6282277721042"},
            "👶 Hiro (新人)": {"id": "6aY1w", "phone": "6282342432368"}
        }

# 1. 載入設備
DEVICES = load_devices_from_csv()

# 2. 初始化人設
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
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        return res.json()
    except:
        return {"code": 500}

def get_real_status(image_id):
    """
    🔍 精準狀態判斷
    """
    # 步驟 1: 基礎連線
    res_ls = send_adb(image_id, "ls")
    if res_ls.get('code') != 200:
        return "🔴 關機中", "stopped"

    # 步驟 2: 檢查系統啟動
    res_boot = send_adb(image_id, "getprop sys.boot_completed")
    boot_val = res_boot.get('data', {}).get(image_id, "").strip()
    
    if boot_val != "1":
        return "🟡 開機中", "booting"
    
    # 步驟 3: 檢查 App
    res_app = send_adb(image_id, "dumpsys window windows | grep mFocusedApp")
    app_out = res_app.get('data', {}).get(image_id, "")
    
    if "com.whatsapp" in app_out:
        return "🟢 執行中 (WhatsApp)", "running"
    elif "launcher" in app_out:
        return "🟢 執行中 (桌面)", "running"
    
    return "🟢 執行中", "running"

def power_on_device(device_id):
    url = f"{BASE_URL}/api/v1/device/open"
    headers = {"DuoPlus-API-Key": DUOPLUS_API_KEY, "Content-Type": "application/json"}
    payload = {"device_id": device_id}
    try:
        requests.post(url, headers=headers, json=payload, timeout=5)
    except:
        pass

# ================== 🖥️ 前端頁面 ==================

st.set_page_config(page_title="DuoPlus 戰情中心", layout="wide", page_icon="📱")

with st.sidebar:
    st.title("🎛️ 中控面板")
    st.info(f"監控設備數: {len(DEVICES)} 台")
    
    if st.button("🔄 全機刷新"):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 📡 Colab 訊號")
    colab_data = get_colab_status()
    if colab_data:
        msg = colab_data.get("message", "無訊號")
        if colab_data.get("last_update"):
            st.success(f"✅ {msg}")
        else:
            st.info(msg)
    else:
        st.error("Colab 失聯 ❌")

st.title("🤖 DuoPlus 雲手機戰情中心 v4.3")
st.caption("Mode: Stable Fix | Source: CSV")

# ================== 📄 分頁邏輯 (修復重點) ==================

# 1. 確保 device_list 被正確定義
device_list = list(DEVICES.items())
DEVICES_PER_PAGE = 8

# 2. 計算總頁數
if len(device_list) > 0:
    total_pages = (len(device_list) - 1) // DEVICES_PER_PAGE + 1
else:
    total_pages = 1

# 3. 顯示滑桿
if total_pages > 1:
    page = st.slider("選擇頁數", 1, total_pages, 1)
else:
    page = 1

# 4. 切割名單 (Slicing)
start_idx = (page - 1) * DEVICES_PER_PAGE
end_idx = min(start_idx + DEVICES_PER_PAGE, len(device_list))
current_page_devices = device_list[start_idx:end_idx]

# ================== 👁️ 監控畫面 ==================

tab_monitor, tab_ai = st.tabs(["👁️ 實時監控", "🧠 AI 設定"])

with tab_monitor:
    st.markdown(f"### 顯示第 {start_idx+1} - {end_idx} 台")
    
    # 平行處理抓取狀態
    status_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_id = {executor.submit(get_real_status, info['id']): info['id'] for name, info in current_page_devices}
        for future in concurrent.futures.as_completed(future_to_id):
            d_id = future_to_id[future]
            status_map[d_id] = future.result()

    cols = st.columns(4)
    
    for i, (name, info) in enumerate(current_page_devices):
        dev_id = info['id']
        col_idx = i % 4
        
        # 取得狀態
        status_text, status_code = status_map.get(dev_id, ("⏳ 讀取中...", "loading"))
        
        with cols[col_idx]:
            with st.container(border=True):
                st.subheader(name)
                st.caption(f"ID: {dev_id}")
                
                # 狀態顯示
                if status_code == "running":
                    st.success(status_text)
                elif status_code == "booting":
                    st.warning(status_text)
                elif status_code == "stopped":
                    st.error(status_text)
                else:
                    st.info(status_text)
                
                # 按鈕
                if status_code == "stopped":
                    if st.button("⚡ 開機", key=f"pwr_{dev_id}", type="primary"):
                        power_on_device(dev_id)
                        st.info("指令發送")
                        time.sleep(2)
                        st.rerun()
                else:
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

with tab_ai:
    if 'personas' not in st.session_state:
        st.session_state['personas'] = DEFAULT_PERSONAS.copy()
    
    for name, info in current_page_devices:
        d_id = info['id']
        if d_id not in st.session_state['personas']:
            st.session_state['personas'][d_id] = "Casual user."
        
        with st.expander(f"設定 {name}"):
            st.session_state['personas'][d_id] = st.text_area(f"Prompt", st.session_state['personas'][d_id], height=70, key=f"ai_{d_id}")

st.divider()
tz = pytz.timezone('Asia/Taipei')
st.caption(f"Server Time: {datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')}")
