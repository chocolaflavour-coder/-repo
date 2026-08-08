# streamlit_app.py
import streamlit as st
from google.oauth2 import service_account
import gspread
import base64

st.set_page_config(page_title="App Google Sheets", layout="centered")
st.title("تطبيق إدارة المنتجات - Google Sheets")

# --- قراءة المفتاح (يدعم multiline أو Base64) ---
def load_private_key():
    pk = st.secrets.get("PRIVATE_KEY")
    if pk:
        return pk
    pk_b64 = st.secrets.get("PRIVATE_KEY_B64")
    if pk_b64:
        return base64.b64decode(pk_b64).decode("utf-8")
    return None

# --- تجهيز بيانات الاعتماد من Secrets ---
def build_service_account_info():
    info = {
        "type": st.secrets.get("TYPE"),
        "project_id": st.secrets.get("PROJECT_ID"),
        "private_key_id": st.secrets.get("PRIVATE_KEY_ID"),
        "private_key": load_private_key(),
        "client_email": st.secrets.get("CLIENT_EMAIL"),
        "client_id": st.secrets.get("CLIENT_ID"),
        "auth_uri": st.secrets.get("AUTH_URI"),
        "token_uri": st.secrets.get("TOKEN_URI"),
        "auth_provider_x509_cert_url": st.secrets.get("AUTH_PROVIDER_CERT_URL"),
        "client_x509_cert_url": st.secrets.get("CLIENT_CERT_URL"),
    }
    return info

# --- إنشاء Credentials والاتصال بـ Google Sheets ---
def get_gspread_client():
    info = build_service_account_info()
    missing = [k for k, v in info.items() if not v]
    if missing:
        raise RuntimeError("متغيرات مفقودة في Secrets: " + ", ".join(missing))
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)

# --- واجهة بسيطة لاختبار الاتصال وقراءة الشيت ---
st.header("اختبار الاتصال وفتح Google Sheet")
if st.button("افتح الشيت الآن"):
    try:
        gc = get_gspread_client()
        sheet_id = st.secrets.get("TEST_SHEET_ID")
        if not sheet_id:
            st.error("لم يتم تحديد TEST_SHEET_ID في Secrets.")
        else:
            sh = gc.open_by_key(sheet_id)
            st.success("تم الوصول إلى الشيت: " + sh.title)
            # مثال: قراءة أول ورقة وصفوفها الأولى
            ws = sh.get_worksheet(0)
            rows = ws.get_all_values()[:10]
            st.write("أول 10 صفوف من الورقة الأولى:")
            st.table(rows)
    except Exception as e:
        st.error("فشل الاتصال أو فتح الشيت: " + str(e))

# --- واجهة لإدارة المنتجات (نموذج مبسط) ---
st.header("تحديث منتج (نموذج مبسط)")
with st.form("update_form"):
    product_query = st.text_input("اسم المنتج أو الباركود")
    new_qty = st.number_input("الكمية الجديدة", min_value=0, step=1)
    new_valid = st.selectbox("الحالة (صالحة/منتهية)", ["صالحة", "منتهية"])
    submitted = st.form_submit_button("تحديث")
    if submitted:
        try:
            gc = get_gspread_client()
            sheet_id = st.secrets.get("TEST_SHEET_ID")
            sh = gc.open_by_key(sheet_id)
            ws = sh.get_worksheet(0)
            data = ws.get_all_values()
            # بحث بسيط عن المنتج في العمود الأول (يمكن تعديل حسب الشيت)
            updated = False
            for i, row in enumerate(data, start=1):
                if len(row) > 0 and product_query.strip() and product_query.strip() in row[0]:
                    # مثال: افترض أن الكمية في العمود 3 والحالة في العمود 4 (1-indexed)
                    ws.update_cell(i, 3, str(new_qty))
                    ws.update_cell(i, 4, new_valid)
                    updated = True
            if updated:
                st.success("تم تحديث المنتج بنجاح.")
            else:
                st.info("لم يتم العثور على المنتج.")
        except Exception as e:
            st.error("حدث خطأ أثناء التحديث: " + str(e))
