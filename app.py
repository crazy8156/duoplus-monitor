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
        return {
            "👑 MyWA (老闆)": {"id": "1ZxjQ", "phone": "886916802803"},
            "💄 Aiko (美妝)": {"id": "F8Z5z", "phone": "6281299393526"},
            "🎮 Jiarong (電玩)": {"id": "TkRrq", "phone": "6282277721042"},
            "👶 Hiro (新人)": {"id": "6aY1w", "phone": "6282342432368"}
        }

DEVICES = load_devices_from_csv()

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
    🔍 精準狀態判斷邏輯
    1. 先 Ping (ls) -> 失敗就是「🔴 關機中」
    2. 檢查 boot_completed -> 不是 1 就是「🟡 開機中」
    3. 如果都通過 -> 就是「🟢 執行中」
    """
    # 步驟 1: 基礎連線測試
    res_ls = send_adb(image_id, "ls")
    if res_ls.get('code') != 200:
        return "🔴 關機中", "stopped"

    # 步驟 2: 檢查系統是否完全啟動
    res_boot = send_adb(image_id, "getprop sys.boot_completed")
    boot_val = res_boot.get('data', {}).get(image_id, "").strip()
    
    if boot_val != "1":
        return "🟡 開機中", "booting"
    
    # 步驟 3: 額外檢查 (是否在 WhatsApp)
    # 這裡我們只做加分項，如果抓不到就顯示「執行中」，絕不顯示「未知」
    res_app = send_adb(image_id, "dumpsys window windows | grep mFocusedApp")
    app_out = res_app.get('data', {}).get(image_id, "")
    
    if "com.whatsapp" in app_out:
        return "🟢 執行中 (WhatsApp)", "running"
    elif "launcher" in app_out:
        return "🟢 執行中 (桌面)", "running"
    
    # 預設回傳
    return "🟢 執行中", "running"

def power_on_device(device_id):
    url = f"{BASE_URL}/api/v1/device/open"
    headers = {"DuoPlus-API-Key": DUOPLUS_API_KEY, "Content-Type": "application/json"}
    payload = {"device_id": device_id}
    requests.post(url, headers=headers, json=payload, timeout=5)

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

st.title("🤖 DuoPlus 雲手機戰情中心 v4.2")
st.caption("Mode: Precise Status | Source: CSV")

# 分頁控制
DEVICES_PER_PAGE = 8
device
