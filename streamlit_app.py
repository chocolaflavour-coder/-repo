import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.title("🧪 اختبار الاتصال البسيط بجوجل شيت")

try:
    # 1. جلب البيانات من الـ Secrets بنجاح
  creds_dict = st.secrets["gcp_service_account"]
GOOGLE_SHEET_ID = st.secrets["sheet_id"]

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)

sheet = client.open_by_key(GOOGLE_SHEET_ID)
products_sheet = sheet.worksheet("المنتجات")
first_value = products_sheet.acell('A1').value

    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # 3. فتح الملف وقراءة أول خلية
    sheet = client.open_by_key(GOOGLE_SHEET_ID)
    products_sheet = sheet.worksheet("المنتجات")
    first_value = products_sheet.acell('A1').value
    
    st.success(f"🎉 كفوووو يا بطل! تم الاتصال بنجاح تام! أول قيمة في الشيت هي: ({first_value})")

except Exception as e:
    st.error(f"❌ فشل الاتصال! سبب المشكلة المكتوب هو:\n\n`{str(e)}`")
