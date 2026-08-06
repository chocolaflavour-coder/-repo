import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import re

st.title("🧪 اختبار الاتصال البسيط بجوجل شيت")

# 🔗 الحيلة الذكية: وضع رابط الشيت كاملاً، وسيتكفل الكود باستخراج المعرف لحل مشكلة الـ 404
FULL_SHEET_URL = "https://google.com"

try:
    # 1. جلب وتنظيف الـ Secrets
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    
    # 2. الاتصال بـ Google
    scopes = ["https://googleapis.com", "https://googleapis.com"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # 3. فتح الملف باستخدام الرابط الكامل مباشرة
    sheet = client.open_by_url(FULL_SHEET_URL)
    products_sheet = sheet.worksheet("المنتجات")
    first_value = products_sheet.acell('A1').value
    
    st.success(f"🎉 كفوووو يا بطل! تم الاتصال بنجاح تام! أول قيمة في الشيت هي: ({first_value})")

except Exception as e:
    st.error(f"❌ فشل الاتصال! سبب المشكلة المكتوب هو:\n\n`{str(e)}`")
