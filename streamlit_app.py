import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.title("🧪 اختبار الاتصال البسيط بجوجل شيت")

# ⚠️ تأكد من كتابة هذا السطر هكذا تماماً وبدون تمرير أي حقول قديمة
conn = st.connection("gsheets", type=GSheetsConnection)

# قراءة البيانات مباشرة (ستعتمد تلقائياً على الرابط الموجود في السيكريت)
try:
    df = conn.read()
    st.success("تم الاتصال وجلب البيانات بنجاح!")
    st.dataframe(df)
except Exception as e:
    st.error(f"فشل الاتصال! سبب المشكلة هو:\n\n{e}")
