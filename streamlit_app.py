import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import re

# --- 基礎設定 ---
st.set_page_config(page_title="Decathlon Office Booking", layout="wide", page_icon="🏢")

# 定義各 Office 容量
OFFICE_CAPACITY = {
    "TKO Office": 20,
    "ST Office": 10,
    "CTR Office": 10
}

# --- CSS 美化 ---
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 連接 Google Sheets ---
# 請確保 .streamlit/secrets.toml 已設定好連結
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    # ttl=0 代表不緩存，每次重新整理都抓最新資料
    return conn.read(worksheet="Bookings", ttl="0")

# 取得最新資料
try:
    df = get_data()
except Exception as e:
    st.error("無法讀取 Google Sheet，請檢查 secrets 設定或網路連線。")
    df = pd.DataFrame(columns=["Date", "Office", "Name", "Email"])

# --- 側邊欄：預訂表單 ---
st.sidebar.header("📝 新增辦公室預訂")

with st.sidebar.form("booking_form", clear_on_submit=True):
    user_name = st.text_input("您的姓名 (Name)")
    user_email = st.text_input("Decathlon Email", placeholder="example@decathlon.com")
    
    selected_date = st.date_input("預訂日期", min_value=datetime.today())
    selected_office = st.selectbox("選擇地點", list(OFFICE_CAPACITY.keys()))
    
    submit_button = st.form_submit_button("確認提交")

    if submit_button:
        date_str = selected_date.strftime("%Y-%m-%d")
        email_pattern = r"^[a-zA-Z0-9._%+-]+@decathlon\.com$"
        
        # 1. 基本欄位檢查
        if not user_name or not user_email:
            st.sidebar.warning("⚠️ 請填寫所有欄位")
        
        # 2. Email 格式檢查
        elif not re.match(email_pattern, user_email.lower()):
            st.sidebar.error("❌ 格式錯誤！請使用 @decathlon.com 電郵")
            
        else:
            # 3. 檢查當天該 Office 是否已滿
            office_day_data = df[(df['Date'] == date_str) & (df['Office'] == selected_office)]
            current_count = len(office_day_data)
            
            # 4. 檢查同一個人是否重複預訂同一天
            duplicate_check = df[(df['Date'] == date_str) & (df['Email'] == user_email.lower())]
            
            if not duplicate_check.empty:
                st.sidebar.warning(f"⚠️ 您在 {date_str} 已經有預訂紀錄了")
                
            elif current_count >= OFFICE_CAPACITY[selected_office]:
                st.sidebar.error(f"❌ 很抱歉，{selected_office} 在這天已經滿座！")
                
            else:
                # 寫入資料
                new_data = pd.DataFrame([{
                    "Date": date_str,
                    "Office": selected_office,
                    "Name": user_name,
                    "Email": user_email.lower()
                }])
                
                updated_df = pd.concat([df, new_data], ignore_index=True)
                conn.update(worksheet="Bookings", data=updated_df)
                
                st.sidebar.success(f"🎉 預訂成功！日期：{date_str}")
                st.rerun()

# --- 主畫面：Dashboard ---
st.title("📊 Office Occupancy Dashboard")

# 日期篩選器
view_date = st.date_input("查看特定日期狀況", value=datetime.today())
view_date_str = view_date.strftime("%Y-%m-%d")

st.divider()

# 顯示三間 Office 的數據
cols = st.columns(3)
day_data = df[df['Date'] == view_date_str]

for i, (office, capacity) in enumerate(OFFICE_CAPACITY.items()):
    booked = len(day_data[day_data['Office'] == office])
    vacant = capacity - booked
    occupancy_rate = (booked / capacity) * 100
    
    with cols[i]:
        st.subheader(office)
        # 使用 Metric 顯示人數
        st.metric(label="已預訂 / 總位子", value=f"{booked} / {capacity}", delta=f"剩餘 {vacant}", delta_color="normal")
        
        # 進度條顯示擁擠程度
        bar_color = "green" if occupancy_rate < 80 else "red"
        st.progress(booked / capacity)
        st.caption(f"目前佔用率: {occupancy_rate:.1f}%")

# --- 預訂明細表 ---
st.divider()
st.subheader(f"📅 {view_date_str} 預訂清單")

if not day_data.empty:
    # 隱藏 Email 欄位以保護隱私，只顯示地點與姓名
    display_df = day_data[day_data['Office'].isin(OFFICE_CAPACITY.keys())][['Office', 'Name']]
    st.dataframe(display_df.sort_values("Office"), use_container_width=True)
else:
    st.info("💡 當天目前沒有任何預訂。")

# --- 底部頁尾 ---
st.caption("Developed for Decathlon Team | Data synced with Google Sheets")
