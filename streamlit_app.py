import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import re
import requests
import json

# --- 1. 網頁配置 ---
st.set_page_config(page_title="Decathlon Office Booking", layout="wide", page_icon="🏢")

# 【請在此處替換為你部署後的 Google Apps Script URL】
SCRIPT_URL = "你的_APPS_SCRIPT_URL"

OFFICE_CAPACITY = {
    "TKO Office": 20,
    "ST Office": 10,
    "CTR Office": 10
}

# --- 2. 資料讀取 (修正 HTTP 400 錯誤) ---
def get_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        # 修正 400 錯誤：不指定 worksheet 參數，預設讀取試算表的第一個分頁
        # 確保 Secrets 裡的網址是乾淨的 .../edit#gid=0
        data = conn.read(ttl="0")
        if data is not None and not data.empty:
            return data
        return pd.DataFrame(columns=["Date", "Office", "Name", "Email"])
    except Exception as e:
        st.error(f"⚠️ 讀取資料失敗 (HTTP 400 可能是網址格式問題): {e}")
        return pd.DataFrame(columns=["Date", "Office", "Name", "Email"])

# 執行讀取
df = get_data()

# --- 3. 側邊欄：預訂表單 ---
st.sidebar.header("📝 新增辦公室預訂")

with st.sidebar.form("booking_form", clear_on_submit=True):
    user_name = st.text_input("您的姓名 (Name)")
    user_email = st.text_input("Decathlon Email", placeholder="e.g. name@decathlon.com")
    selected_date = st.date_input("預訂日期", min_value=datetime.today())
    selected_office = st.selectbox("選擇地點", list(OFFICE_CAPACITY.keys()))
    
    submit_button = st.form_submit_button("確認提交")

    if submit_button:
        date_str = selected_date.strftime("%Y-%m-%d")
        email_pattern = r"^[a-zA-Z0-9._%+-]+@decathlon\.com$"
        
        # 基礎欄位檢查
        if not user_name or not user_email:
            st.sidebar.warning("⚠️ 請填寫所有欄位")
        elif not re.match(email_pattern, user_email.lower()):
            st.sidebar.error("❌ 格式錯誤！請使用 @decathlon.com 電郵")
        else:
            # 檢查重複與滿座
            # 強制轉換日期格式確保比較準確
            df_temp = df.copy()
            df_temp['Date'] = df_temp['Date'].astype(str)
            
            day_data = df_temp[df_temp['Date'] == date_str]
            office_count = len(day_data[day_data['Office'] == selected_office])
            is_duplicate = not day_data[day_data['Email'].str.lower() == user_email.lower()].empty
            
            if is_duplicate:
                st.sidebar.warning(f"⚠️ 您在 {date_str} 已經有預訂紀錄")
            elif office_count >= OFFICE_CAPACITY[selected_office]:
                st.sidebar.error(f"❌ {selected_office} 於此日期已滿座")
            else:
                # --- 透過 Apps Script 寫入資料 ---
                payload = {
                    "Date": date_str,
                    "Office": selected_office,
                    "Name": user_name,
                    "Email": user_email.lower()
                }
                
                try:
                    with st.spinner("正在提交至 Google Sheets..."):
                        # 注意：此處不需處理 Apps Script 的 postData 報錯，那是因為手動執行導致的
                        res = requests.post(SCRIPT_URL, data=json.dumps(payload))
                        if res.status_code == 200:
                            st.sidebar.success(f"🎉 預訂成功！({date_str})")
                            # 成功後清除緩存並刷新
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.sidebar.error("寫入失敗，請確認 Apps Script 已部署為「所有人(Anyone)」")
                except Exception as e:
                    st.sidebar.error(f"連線錯誤: {e}")

# --- 4. 主畫面：Dashboard ---
st.title("📊 Office Occupancy Dashboard")

# 日期選擇器
view_date = st.date_input("查看預訂狀況", value=datetime.today())
view_date_str = view_date.strftime("%Y-%m-%d")

st.divider()

# 顯示三間 Office 數據
df['Date'] = df['Date'].astype(str)
current_day_data = df[df['Date'] == view_date_str]

cols = st.columns(3)
for i, (office, cap) in enumerate(OFFICE_CAPACITY.items()):
    booked = len(current_day_data[current_day_data['Office'] == office])
    vacant = cap - booked
    
    with cols[i]:
        st.subheader(office)
        st.metric("已預訂 / 總量", f"{booked} / {cap}", f"剩餘 {vacant}")
        st.progress(booked / cap if cap > 0 else 0)

# --- 5. 預訂名單明細 ---
st.divider()
st.subheader(f"📅 {view_date_str} 預訂名單")

if not current_day_data.empty:
    # 僅顯示 Office 和 Name，保護 Email 隱私
    display_df = current_day_data[['Office', 'Name']].sort_values("Office")
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.info("💡 該日期暫時沒有任何預訂。")

# 頁尾資訊
st.caption(f"數據同步時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
