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
    st.error("⚠️ API Key 未設定")
    st.stop()

# 1. 狀態信箱 (舊的，不用動)
COLAB_STATUS_URL = "https://jsonblob.com/api/jsonBlob/019abe39-7045-7d9d-baa4-ef73f78f2a8e"

# 2. 🔥 設定檔信箱 (新的！請填入第一步產生的網址)
CONFIG_URL = "https://jsonblob.com/api/jsonBlob/019ac3d7-5f4e-720b-b226-1619a6118f43"

client = OpenAI(api_key=OPENAI_API_KEY)

# ================== 📂 設備載入系統 (CSV) ==================
@st.cache_data
def load_devices_from_csv():
    try:
        df = pd.read_csv("devices.csv")
        df.columns = [c.strip() for c in df.columns]
        devices = {}
        for index, row in df.iterrows():
            d_id = str(row.get('ID', '')).strip()
            name = str(row.get('名稱', f'Device_{index}')).strip()
            remark = str(row.get('備註', '')).strip()
            phone = remark if remark.startswith('62') or remark.startswith('886') else "Unknown"
            if d_id: devices[name] = {"id": d_id, "phone": phone}
        return devices
    except:
        return { "MyWA": {"id": "1ZxjQ", "phone": "886916802803"} } # 預設

DEVICES = load_devices_from_csv()

# ================== 🔧 後端函數 ==================

def get_config():
    """讀取目前的廣告設定"""
    try: return requests.get(CONFIG_URL).json()
    except: return {}

def update_config(promo_msg, video_urls_str):
    """更新廣告設定"""
    # 把字串轉回 list
    video_list = [x.strip() for x in video_urls_str.split('\n') if x.strip()]
    data = {
        "promo_msg": promo_msg,
        "video_urls": video_list,
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    requests.put(CONFIG_URL, json=data)

def get_colab_status():
    try: return requests.get(COLAB_STATUS_URL, timeout=3).json()
    except: return None

def send_adb(image_id, cmd):
    url = f"{BASE_URL}/api/v1/cloudPhone/command"
    headers = {"DuoPlus-API-Key": DUOPLUS_API_KEY, "Content-Type": "application/json"}
    try:
        res = requests.post(url, headers=headers, json={"image_ids": [image_id], "command": cmd}, timeout=5)
        return res.json() if res.status_code == 200 else {"code": 500}
    except: return {"code": 500}

def safe_get_data(res, image_id):
    if not res or not isinstance(res, dict): return ""
    return str(res.get('data', {}).get(image_id, "")).strip()

def get_real_status(image_id):
    res_ls = send_adb(image_id, "ls /system")
    ls_data = safe_get_data(res_ls, image_id).lower()
    error_keywords = ["offline", "not found", "error", "closed", "null", "device"]
    if not ls_data or any(x in ls_data for x in error_keywords) or len(ls_data) < 5:
        return "🔴 關機中", "stopped"
    return "🟢 正常中", "running"

def power_on_device(device_id):
    url = f"{BASE_URL}/api/v1/device/open"
    headers = {"DuoPlus-API-Key": DUOPLUS_API_KEY, "Content-Type": "application/json"}
    requests.post(url, headers=headers, json={"device_id": device_id}, timeout=5)

# ================== 🖥️ 前端頁面 ==================

st.set_page_config(page_title="DuoPlus 戰情中心", layout="wide", page_icon="📱")

with st.sidebar:
    st.title("🎛️ 中控面板")
    if st.button("🔄 全機刷新", use_container_width=True):
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

st.title("🤖 DuoPlus 雲手機戰情中心 v5.0")
st.caption("Mode: CMS Enabled | Source: CSV")

# 分頁邏輯
DEVICES_PER_PAGE = 8
device_list = list(DEVICES.items())
total_pages = (len(device_list) - 1) // DEVICES_PER_PAGE + 1
page = st.slider("選擇頁數", 1, total_pages, 1) if total_pages > 1 else 1
start_idx = (page - 1) * DEVICES_PER_PAGE
current_page_devices = device_list[start_idx : start_idx + DEVICES_PER_PAGE]

# 分頁標籤
tab_monitor, tab_admin, tab_ai = st.tabs(["👁️ 實時監控", "📝 廣告後台", "🧠 AI 設定"])

# === Tab 1: 監控 ===
with tab_monitor:
    status_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_id = {executor.submit(get_real_status, info['id']): info['id'] for name, info in current_page_devices}
        for future in concurrent.futures.as_completed(future_to_id):
            d_id = future_to_id[future]
            try: status_map[d_id] = future.result()
            except: status_map[d_id] = ("🔴 逾時", "stopped")

    cols = st.columns(4)
    for i, (name, info) in enumerate(current_page_devices):
        dev_id = info['id']
        with cols[i % 4]:
            with st.container(border=True):
                st.subheader(name)
                st.caption(f"ID: {dev_id}")
                text, code = status_map.get(dev_id, ("⏳...", "loading"))
                
                if code == "running": st.success(text)
                else: st.error(text)
                
                if code == "stopped":
                    if st.button("⚡ 開機", key=f"p_{dev_id}", type="primary"):
                        power_on_device(dev_id)
                        st.info("指令發送")
                else:
                    st.markdown("---")
                    c1, c2 = st.columns(2)
                    with c1: 
                        if st.button("🏠", key=f"h_{dev_id}"): send_adb(dev_id, "input keyevent 3")
                    with c2: 
                        if st.button("💬", key=f"w_{dev_id}"): send_adb(dev_id, 'am start -a android.intent.action.VIEW -d "https://wa.me/" com.whatsapp')

# === Tab 2: 廣告後台 (新功能) ===
with tab_admin:
    st.header("📢 廣告內容管理")
    st.info("在此修改內容後按儲存，Colab 機器人會在下一輪發送時自動更新。")
    
    # 讀取目前設定
    current_config = get_config()
    current_msg = current_config.get("promo_msg", "")
    current_urls = "\n".join(current_config.get("video_urls", []))
    
    with st.form("promo_form"):
        new_msg = st.text_area("泰文廣告文案 (支援換行/Emoji)", value=current_msg, height=150)
        new_urls = st.text_area("影片/連結庫 (一行一個網址)", value=current_urls, height=100)
        
        if st.form_submit_button("💾 儲存設定並同步"):
            update_config(new_msg, new_urls)
            st.success("✅ 設定已更新！Colab 將自動讀取新內容。")

# === Tab 3: AI 設定 ===
with tab_ai:
    st.info("人設管理")
    if 'personas' not in st.session_state: st.session_state['personas'] = {}
    for name, info in current_page_devices:
        d_id = info['id']
        st.session_state['personas'].setdefault(d_id, "Casual user.")
        with st.expander(f"設定 {name}"):
            st.session_state['personas'][d_id] = st.text_area("Prompt", st.session_state['personas'][d_id], key=f"ai_{d_id}")

st.divider()
st.caption(f"Server Time: {datetime.now().strftime('%H:%M:%S')}")
