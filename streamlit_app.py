# streamlit_app_debug.py
import streamlit as st
from google.oauth2 import service_account
import gspread
import base64
from google.auth.exceptions import GoogleAuthError
import re
from datetime import datetime

st.set_page_config(page_title="Debug - تحديث المنتجات", layout="centered")
st.title("تشخيص إضافة التحديثات")

def load_private_key():
    pk = st.secrets.get("PRIVATE_KEY")
    if pk:
        return pk
    pk_b64 = st.secrets.get("PRIVATE_KEY_B64")
    if pk_b64:
        return base64.b64decode(pk_b64).decode("utf-8")
    return None

def build_service_account_info():
    return {
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

def get_gspread_client():
    info = build_service_account_info()
    missing = [k for k, v in info.items() if not v]
    if missing:
        raise RuntimeError("متغيرات مفقودة في Secrets: " + ", ".join(missing))
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)

def open_products_ws():
    gc = get_gspread_client()
    # حاول فتح بالاسم أولاً، ثم بالمفتاح إن وُجد
    try:
        sh = gc.open("المنتجات")
    except Exception as e:
        sheet_key = st.secrets.get("TEST_SHEET_ID")
        if sheet_key:
            sh = gc.open_by_key(sheet_key)
        else:
            raise RuntimeError("لم أجد ملف باسم 'المنتجات' ولم يتم توفير TEST_SHEET_ID.")
    ws = sh.get_worksheet(0)
    return gc, sh, ws

st.markdown("### اختبار المصادقة والكتابة")
st.write("تأكد أن `client_email` مشارك كـ Editor على ملف 'المنتجات'.")

if st.button("اختبار إضافة صف تجريبي إلى 'المنتجات'"):
    try:
        gc, sh, ws = open_products_ws()
        test_row = ["TEST-BARCODE-DEBUG", "TEST-PRODUCT-DEBUG", "2099-01-01", "1", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
        st.write("محاولة إضافة الصف:", test_row)
        ws.append_row(test_row, value_input_option="USER_ENTERED")
        st.success("نجح: تم إضافة الصف التجريبي إلى 'المنتجات'. تحقق في الشيت.")
    except Exception as e:
        st.error("فشل أثناء محاولة إضافة الصف التجريبي.")
        st.exception(e)
