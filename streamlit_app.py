import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.title("🧪 اختبار الاتصال البسيط بجوجل شيت")

try:
    # 1. جلب البيانات من الـ Secrets بنجاح
    creds_dict = dict(st.secrets["gcp_service_account"])
    GOOGLE_SHEET_ID = st.secrets["sheet_id"]
    
    # 🛠️ الحيلة السحرية: تنظيف المفتاح وتركيب الترويسة الرسمية آلياً لتفادي خطأ الـ InvalidHeader
    if "private_key" in creds_dict:
        key = creds_dict["private_key"].strip()
        # تنظيف أي علامات تنصيص أو أسطر مائلة زائدة
        key = key.replace("\\n", "\n").replace('"', '').replace("'", "")
        
        # إذا كان المفتاح الملصوق لا يحتوي على الترويسة الرسمية، نقوم بتركيبها برمجياً
        if "-----BEGIN PRIVATE KEY-----" not in key:
                 key = key.replace("\n", "\n").replace('', '').replace('', '')

            
        creds_dict["private_key"] = key
    
    # 2. الاتصال الفعلي بجوجل
   scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # 3. فتح الملف وقراءة أول خلية
    sheet = client.open_by_key(GOOGLE_SHEET_ID)
    products_sheet = sheet.worksheet("المنتجات")
    first_value = products_sheet.acell('A1').value
    
    st.success(f"🎉 كفوووو يا بطل! تم الاتصال بنجاح تام! أول قيمة في الشيت هي: ({first_value})")

except Exception as e:
    st.error(f"❌ فشل الاتصال! سبب المشكلة المكتوب هو:\n\n`{str(e)}`")
