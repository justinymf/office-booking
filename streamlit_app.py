import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import re
import requests
import json

# --- 1. 基礎設定 ---
st.set_page_config(page_title="Decathlon Office Booking", layout="wide", page_icon="🏢")

# 【請替換為你的 Apps Script URL】
SCRIPT_URL = "你的_APPS_SCRIPT_URL_貼在這裡"

OFFICE_CAPACITY = {
    "TKO Office": 20,
    "ST Office": 10,
    "CTR Office": 10
}

# --- 2. 資料讀取函數 ---
# 使用 st.cache_data 並配合一個手動刷新的觸發器
def get_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        # ttl="0" 確保每次重新整理網頁都會抓最新資料
        data = conn.read(worksheet="Bookings", ttl="0")
        return data
    except Exception as e:
        st.error(f"讀取資料失敗: {e}")
        return pd.DataFrame(columns=["Date", "Office", "Name", "Email"])

# 取得最新資料
df = get_data()

# --- 3. 側邊欄：預訂表單 ---
st.sidebar.header("📝 新增辦公室預訂")

with st.sidebar.form("booking_form", clear_on_submit=True):
    user_name = st.text_input("您的姓名 (Name)")
    user_email = st.text_input("Decathlon Email", placeholder="e.g. justin.yip@decathlon.com")
    selected_date = st.date_input("預訂日期", min_value=datetime.today())
    selected_office = st.selectbox("選擇地點", list(OFFICE_CAPACITY.keys()))
    
    submit_button = st.form_submit_button("確認提交")

    if submit_button:
        date_str = selected_date.strftime("%Y-%m-%d")
        email_pattern = r"^[a-zA-Z0-9._%+-]+@decathlon\.com$"
        
        # 基本檢查
        if not user_name or not user_email:
            st.sidebar.warning("⚠️ 請填寫所有欄位")
        elif not re.match(email_pattern, user_email.lower()):
            st.sidebar.error("❌ 格式錯誤！請使用 @decathlon.com 電郵")
        else:
            # 檢查當天該 Office 狀況
            # 確保 df 裡面的 Date 格式與搜尋的一致
            df['Date'] = df['Date'].astype(str)
            day_data = df[df['Date'] == date_str]
            
            office_count = len(day_data[day_data['Office'] == selected_office])
            is_duplicate = not day_data[day_data['Email'].str.lower() == user_email.lower()].empty
            
            if is_duplicate:
                st.sidebar.warning(f"⚠️ 您在 {date_str} 已經有預訂紀錄了")
            elif office_count >= OFFICE_CAPACITY[selected_office]:
                st.sidebar.error(f"❌ 很抱歉，{selected_office} 在這天已經滿座！")
            else:
                # --- 執行 Apps Script 寫入 ---
                payload = {
                    "Date": date_str,
                    "Office": selected_office,
                    "Name": user_name,
                    "Email": user_email.lower()
                }
                
                with st.spinner("提交中..."):
                    try:
                        res = requests.post(SCRIPT_URL, data=json.dumps(payload))
                        if res.status_code == 200:
                            st.sidebar.success(f"🎉 預訂成功！日期：{date_str}")
                            # 成功後強制刷新頁面以更新 Dashboard
                            st.rerun()
                        else:
                            st.sidebar.error("寫入失敗，請檢查 Apps Script 的部署權限 (需設為 Anyone)")
                    except Exception as e:
                        st.sidebar.error(f"連線錯誤: {e}")

# --- 4. 主畫面：Dashboard ---
st.title("📊 Office Occupancy Dashboard")

# 日期篩選器
view_date = st.date_input("查看特定日期狀況", value=datetime.today())
view_date_str = view_date.strftime("%Y-%m-%d")

st.divider()

# 計算該日數據
df['Date'] = df['Date'].astype(str)
current_day_data = df[df['Date'] == view_date_str]

cols = st.columns(3)
for i, (office, cap) in enumerate(OFFICE_CAPACITY.items()):
    booked = len(current_day_data[current_day_data['Office'] == office])
    vacant = cap - booked
    occupancy_rate = (booked / cap)
    
    with cols[i]:
        st.subheader(office)
        st.metric("已預訂 / 總位子", f"{booked} / {cap}", f"剩餘 {vacant} 位")
        st.progress(occupancy_rate)

# --- 5. 預訂明細表 ---
st.divider()
st.subheader(f"📅 {view_date_str} 預訂名單")

if not current_day_data.empty:
    # 隱藏 Email 欄位以保護隱私
    display_df = current_day_data[['Office', 'Name']].sort_values("Office")
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.info("💡 當天目前沒有任何預訂。")

st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
