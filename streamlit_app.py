import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.title("🧪 اختبار الاتصال البسيط بجوجل شيت")

GOOGLE_SHEET_ID = "1MOuwq51Y-Odvn9F7k4C5IVkGBDfPlS-HBUh7fVw6Rok"

try:
    # قراءة الأسرار التي جهزتها في ملف secrets.toml بنجاح
    creds_dict = st.secrets["gcp_service_account"]
    scopes = ["https://googleapis.com", "https://googleapis.com"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # فتح الملف وقراءة أول خلية
    sheet = client.open_by_key(GOOGLE_SHEET_ID)
    products_sheet = sheet.worksheet("المنتجات")
    first_value = products_sheet.acell('A1').value
    
    st.success(f"🎉 مبروك! تم الاتصال بنجاح. أول قيمة في الشيت هي: ({first_value})")

except Exception as e:
    st.error(f"❌ فشل الاتصال! سبب المشكلة المكتوب في السيرفر هو:\n\n`{str(e)}`")
