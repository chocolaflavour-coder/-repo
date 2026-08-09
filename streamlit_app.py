# streamlit_app.py
import streamlit as st
from google.oauth2 import service_account
import gspread
import base64

st.set_page_config(page_title="بحث المنتجات - Google Sheets", layout="centered")
st.title("بحث المنتجات")

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

# --- فتح الشيت وجلب البيانات ---
def open_sheet_and_get_data():
    gc = get_gspread_client()
    sheet_id = st.secrets.get("TEST_SHEET_ID")
    if not sheet_id:
        raise RuntimeError("لم يتم تحديد TEST_SHEET_ID في Secrets.")
    sh = gc.open_by_key(sheet_id)
    ws = sh.get_worksheet(0)
    data = ws.get_all_values()
    return ws, data, sh

# --- واجهة البحث البسيطة ---
st.header("ابحث باسم المنتج أو الصق الباركود هنا")

query = st.text_input("اسم المنتج أو الباركود")
if st.button("بحث"):
    if not query or not query.strip():
        st.info("الرجاء إدخال اسم المنتج أو الباركود ثم اضغط بحث.")
    else:
        try:
            ws, data, sh = open_sheet_and_get_data()
            q = query.strip()
            # افتراض الأعمدة: الاسم في العمود 1، الباركود في العمود 2
            NAME_COL = 1
            BARCODE_COL = 2

            exact_barcode_matches = []
            name_matches = []

            for i, row in enumerate(data, start=1):
                row_name = row[NAME_COL - 1] if len(row) >= NAME_COL else ""
                row_barcode = row[BARCODE_COL - 1] if len(row) >= BARCODE_COL else ""
                # باركود يجب أن يكون مطابق 100%
                if row_barcode and q == row_barcode:
                    exact_barcode_matches.append((i, row))
                # اسم: تطابق جزئي غير حساس لحالة الأحرف
                elif row_name and q.lower() in row_name.lower():
                    name_matches.append((i, row))

            # عرض النتائج
            if exact_barcode_matches:
                st.success(f"تم العثور على {len(exact_barcode_matches)} نتيجة مطابقة للباركود (مطابقة 100%).")
                # عرض كل صف كامل كجدول
                rows_to_show = []
                for r_idx, r in exact_barcode_matches:
                    display = {"صف": r_idx}
                    # ضم كل خلايا الصف في أعمدة مفصولة
                    for col_idx, cell in enumerate(r, start=1):
                        display[f"عمود {col_idx}"] = cell
                    rows_to_show.append(display)
                st.table(rows_to_show)
            elif name_matches:
                st.success(f"تم العثور على {len(name_matches)} نتيجة تطابق بالاسم.")
                rows_to_show = []
                for r_idx, r in name_matches:
                    display = {"صف": r_idx}
                    for col_idx, cell in enumerate(r, start=1):
                        display[f"عمود {col_idx}"] = cell
                    rows_to_show.append(display)
                st.table(rows_to_show)
            else:
                st.info("لم يتم العثور على نتائج مطابقة.")
        except Exception as e:
            st.error("حدث خطأ أثناء البحث: " + str(e))
