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
        # 截圖資料量大，timeout 設定為 15 秒
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        return res.json()
    except Exception as e:
        return {"code": 500, "message": str(e)}

def get_screenshot_stable(image_id):
    """📸 穩定版截圖 (兩步法)"""
    # 步驟 1: 先截圖存到手機 (避免 pipe 緩衝區問題)
    cmd_cap = "screencap -p /data/local/tmp/screen.png"
    send_adb(image_id, cmd_cap)
    
    # 步驟 2: 讀取檔案轉 Base64
    cmd_read = "cat /data/local/tmp/screen.png | base64 -w 0"
    res = send_adb(image_id, cmd_read)
    
    # 步驟 3: 清理檔案 (非同步，發了就不管)
    # threading.Thread(target=send_adb, args=(image_id, "rm /data/local/tmp/screen.png")).start()
    
    try:
        if res.get('code') == 200:
            # 取得回傳的字串
            raw_output = res.get('data', {}).get(image_id, "")
            
            # 簡單除錯：如果回傳太短，肯定不是圖片
            if len(raw_output) < 100:
                print(f"截圖失敗 (資料過短): {raw_output}")
                return None
                
            # 嘗試解碼
            return base64.b64decode(raw_output)
    except Exception as e:
        print(f"截圖解析錯誤: {e}")
        return None
    return None

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
    
    # === 🔥 自動監控開關 ===
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
st.title("🤖 DuoPlus 雲手機戰情中心 v3.5")
st.caption("Mode: Hybrid Cloud | Auto-Monitor: " + ("ON" if auto_refresh_mode else "OFF"))

# 🔥 自動抓圖邏輯 (放在最前面執行)
if auto_refresh_mode:
    with st.spinner("⚡ 自動同步畫面中..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_map = {executor.submit(get_screenshot_stable, info['id']): info['id'] for name, info in DEVICES.items()}
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
                
                # 圖片顯示區
                img_key = f"img_{dev_id}"
                if img_key in st.session_state:
                    st.image(st.session_state[img_key], caption="最新畫面", use_container_width=True)
                else:
                    st.info("尚無畫面")

                # 操作按鈕
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("📸", key=f"s_{dev_id}", help="手動截圖"):
                        img = get_screenshot_stable(dev_id)
                        if img:
                            st.session_state[img_key] = img
                            st.rerun() # 抓完立刻刷新
                        else:
                            st.error("截圖失敗")
                with c2:
                    if st.button("🏠", key=f"h_{dev_id}"):
                        send_adb(dev_id, "input keyevent 3")
                        st.toast("已按 Home")
