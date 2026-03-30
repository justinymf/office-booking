import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import re
import requests
import json

# --- 基礎設定 ---
st.set_page_config(page_title="Decathlon Office Booking", layout="wide", page_icon="🏢")

# 填入你剛才部署得到的 Apps Script URL
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwm1a1V2mAO9Y-L5oHXFo34AsGkh5U41qvwEOcFkgC9dKm5O_UdkC2SLpn6o-dvGusmPg/exec"

OFFICE_CAPACITY = {
    "TKO Office": 20,
    "ST Office": 10,
    "CTR Office": 10
}

# --- 連接 Google Sheets (用於讀取 Dashboard) ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        # 讀取時使用 Public URL (Secrets 裡設定的網址)
        return conn.read(worksheet="Bookings", ttl="0")
    except:
        return pd.DataFrame(columns=["Date", "Office", "Name", "Email"])

df = get_data()

# --- 側邊欄：預訂表單 ---
st.sidebar.header("📝 新增預訂")

with st.sidebar.form("booking_form", clear_on_submit=True):
    user_name = st.text_input("您的姓名")
    user_email = st.text_input("Decathlon Email (name@decathlon.com)")
    selected_date = st.date_input("預訂日期", min_value=datetime.today())
    selected_office = st.selectbox("選擇地點", list(OFFICE_CAPACITY.keys()))
    submit_button = st.form_submit_button("確認提交")

    if submit_button:
        date_str = selected_date.strftime("%Y-%m-%d")
        email_pattern = r"^[a-zA-Z0-9._%+-]+@decathlon\.com$"
        
        if not user_name or not user_email:
            st.sidebar.warning("⚠️ 請填寫所有欄位")
        elif not re.match(email_pattern, user_email.lower()):
            st.sidebar.error("❌ 請使用 @decathlon.com Email")
        else:
            # 檢查是否滿座或重複
            day_data = df[df['Date'] == date_str]
            office_count = len(day_data[day_data['Office'] == selected_office])
            is_duplicate = not day_data[day_data['Email'] == user_email.lower()].empty
            
            if is_duplicate:
                st.sidebar.warning(f"⚠️ 您在 {date_str} 已有預訂")
            elif office_count >= OFFICE_CAPACITY[selected_office]:
                st.sidebar.error(f"❌ {selected_office} 已滿座")
            else:
                # --- 使用 Apps Script API 寫入 ---
                payload = {
                    "Date": date_str,
                    "Office": selected_office,
                    "Name": user_name,
                    "Email": user_email.lower()
                }
                try:
                    res = requests.post(SCRIPT_URL, data=json.dumps(payload))
                    if res.status_code == 200:
                        st.sidebar.success("🎉 預訂成功！")
                        st.rerun()
                    else:
                        st.sidebar.error("寫入失敗，請檢查 Script 權限")
                except Exception as e:
                    st.sidebar.error(f"連線錯誤: {e}")

# --- 主畫面：Dashboard ---
st.title("📊 Office Occupancy Dashboard")
view_date = st.date_input("查看日期", value=datetime.today())
view_date_str = view_date.strftime("%Y-%m-%d")

day_data = df[df['Date'] == view_date_str]
cols = st.columns(3)

for i, (office, cap) in enumerate(OFFICE_CAPACITY.items()):
    booked = len(day_data[day_data['Office'] == office])
    vacant = cap - booked
    with cols[i]:
        st.subheader(office)
        st.metric("已預訂", f"{booked} / {cap}", f"剩餘 {vacant}")
        st.progress(booked / cap)

st.divider()
st.subheader(f"📅 {view_date_str} 預訂名單")
if not day_data.empty:
    st.dataframe(day_data[['Office', 'Name']], use_container_width=True)
else:
    st.info("當天暫無預訂。")
