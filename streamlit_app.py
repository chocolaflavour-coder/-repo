import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.title("🧪 اختبار الاتصال البسيط بجوجل شيت")

try:
    # 1. جلب بيانات حساب الخدمة + رقم الشيت
    creds_dict = st.secrets["gcp_service_account"]
    GOOGLE_SHEET_ID = st.secrets["sheet_id"]

    # 2. الصلاحيات الصحيحة
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    # 3. إنشاء الاعتماد والاتصال
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)

    # 4. فتح الشيت وقراءة أول خلية
    sheet = client.open_by_key(GOOGLE_SHEET_ID)
    products_sheet = sheet.worksheet("المنتجات")
    first_value = products_sheet.acell('A1').value

    # 5. نجاح الاتصال
    st.success(f"🎉 كفوووو يا بطل! تم الاتصال بنجاح! أول قيمة في الشيت هي: ({first_value})")

except Exception as e:
    st.error(f"❌ فشل الاتصال! سبب المشكلة هو:\n\n`{str(e)}`")
