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

# --- مساعدة: جلب الشيت والبيانات ---
def open_sheet_and_get_data():
    gc = get_gspread_client()
    sheet_id = st.secrets.get("TEST_SHEET_ID")
    if not sheet_id:
        raise RuntimeError("لم يتم تحديد TEST_SHEET_ID في Secrets.")
    sh = gc.open_by_key(sheet_id)
    ws = sh.get_worksheet(0)
    data = ws.get_all_values()
    return ws, data, sh

# --- واجهة بسيطة لاختبار الاتصال وقراءة الشيت ---
st.header("اختبار الاتصال وفتح Google Sheet")
if st.button("افتح الشيت الآن"):
    try:
        ws, data, sh = open_sheet_and_get_data()
        st.success("تم الوصول إلى الشيت: " + sh.title)
        rows = data[:10]
        st.write("أول 10 صفوف من الورقة الأولى:")
        st.table(rows)
    except Exception as e:
        st.error("فشل الاتصال أو فتح الشيت: " + str(e))

# --- واجهة لإدارة المنتجات (بحث بالباركود المطابق 100% أو بالاسم مع اختيار) ---
st.header("تحديث منتج (بحث بالباركود أو بالاسم)")

with st.form("update_form"):
    product_query = st.text_input("ادخل اسم المنتج أو الباركود (امسح الباركود بكاميرا الجوال والصقه هنا)")
    new_qty = st.number_input("الكمية الجديدة", min_value=0, step=1)
    new_valid = st.selectbox("الحالة (صالحة/منتهية)", ["صالحة", "منتهية"])
    submitted = st.form_submit_button("تحديث")

    if submitted:
        if not product_query or not product_query.strip():
            st.info("الرجاء إدخال اسم المنتج أو الباركود.")
        else:
            try:
                ws, data, sh = open_sheet_and_get_data()
                query = product_query.strip()
                # افتراض: الاسم في العمود 1، الباركود في العمود 2، الكمية في العمود 3، الحالة في العمود 4
                NAME_COL = 1
                BARCODE_COL = 2
                QTY_COL = 3
                STATUS_COL = 4

                # بناء فهرس للباركودات (مطابقة 100%)
                barcode_to_row = {}
                name_matches = []  # قائمة tuples: (row_index, row)
                for i, row in enumerate(data, start=1):
                    # تأكد من طول الصفوف قبل الوصول للأعمدة
                    row_name = row[NAME_COL - 1] if len(row) >= NAME_COL else ""
                    row_barcode = row[BARCODE_COL - 1] if len(row) >= BARCODE_COL else ""
                    # باركود مطابق 100%
                    if row_barcode and query == row_barcode:
                        barcode_to_row[row_barcode] = (i, row)
                    # بحث اسم جزئي (غير حساس لحالة الأحرف)
                    if row_name and query.lower() in row_name.lower():
                        name_matches.append((i, row))

                # حالة 1: وجد باركود مطابق 100% -> تحديث مباشر
                if barcode_to_row:
                    # نأخذ أول تطابق (من المفترض الباركود فريد)
                    matched_barcode, (row_idx, row) = next(iter(barcode_to_row.items()))
                    # تحديث الخلايا
                    ws.update_cell(row_idx, QTY_COL, str(new_qty))
                    ws.update_cell(row_idx, STATUS_COL, new_valid)
                    st.success(f"تم تحديث المنتج بالباركود {matched_barcode} في الصف {row_idx}.")
                else:
                    # حالة 2: بحث بالاسم -> عرض النتائج للاختيار
                    if not name_matches:
                        st.info("لم يتم العثور على منتج مطابق للاسم.")
                    elif len(name_matches) == 1:
                        # إذا كان هناك نتيجة واحدة، نحدّثها مباشرة بعد تأكيد المستخدم
                        row_idx, row = name_matches[0]
                        display_name = row[NAME_COL - 1] if len(row) >= NAME_COL else "(بدون اسم)"
                        if st.confirm_button := st.button(f"تأكيد تحديث المنتج الوحيد: {display_name} (صف {row_idx})"):
                            ws.update_cell(row_idx, QTY_COL, str(new_qty))
                            ws.update_cell(row_idx, STATUS_COL, new_valid)
                            st.success(f"تم تحديث المنتج '{display_name}' في الصف {row_idx}.")
                    else:
                        # أكثر من نتيجة: اعرض قائمة للاختيار
                        options = []
                        for r_idx, r in name_matches:
                            nm = r[NAME_COL - 1] if len(r) >= NAME_COL else "(بدون اسم)"
                            bc = r[BARCODE_COL - 1] if len(r) >= BARCODE_COL else ""
                            # عرض الاسم والباركود والصف لتمييز النتائج
                            options.append(f"صف {r_idx} - {nm} - باركود: {bc}")
                        choice = st.selectbox("تم العثور على عدة منتجات، اختر المنتج الذي تريد تحديثه:", options)
                        if st.button("تحديث المنتج المحدد"):
                            # استخرج رقم الصف من النص المختار (نمط "صف {r_idx} - ...")
                            try:
                                chosen_row_idx = int(choice.split("-")[0].strip().split()[1])
                                ws.update_cell(chosen_row_idx, QTY_COL, str(new_qty))
                                ws.update_cell(chosen_row_idx, STATUS_COL, new_valid)
                                st.success(f"تم تحديث المنتج في الصف {chosen_row_idx}.")
                            except Exception as ex:
                                st.error("حدث خطأ أثناء محاولة تحديث المنتج المحدد: " + str(ex))

            except Exception as e:
                st.error("حدث خطأ أثناء العملية: " + str(e))
