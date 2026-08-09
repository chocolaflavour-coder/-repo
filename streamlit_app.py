# streamlit_app.py
import streamlit as st
from google.oauth2 import service_account
import gspread
import base64
from google.auth.exceptions import GoogleAuthError

st.set_page_config(page_title="بحث المنتجات", layout="centered")
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
    # نستخدم نطاقين شائعين: Sheets للقراءة/الكتابة و Drive لو احتجنا صلاحيات إضافية لاحقاً
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        return gspread.authorize(creds)
    except GoogleAuthError as gae:
        raise RuntimeError("خطأ في المصادقة: " + str(gae))
    except Exception as e:
        raise RuntimeError("فشل إنشاء عميل gspread: " + str(e))

# --- فتح جدول باسم "المنتجات" وجلب البيانات (تجاهل رأس العمود) ---
def open_products_sheet():
    gc = get_gspread_client()
    try:
        sh = gc.open("المنتجات")
    except Exception as e:
        # حاول فتح بالـ key إذا كان موجودًا في Secrets كبديل
        sheet_key = st.secrets.get("TEST_SHEET_ID")
        if sheet_key:
            try:
                sh = gc.open_by_key(sheet_key)
            except Exception as e2:
                raise RuntimeError("فشل فتح الشيت باسم 'المنتجات' وبالمفتاح: " + str(e2))
        else:
            raise RuntimeError("فشل فتح الشيت باسم 'المنتجات' ولم يتم توفير TEST_SHEET_ID. الخطأ: " + str(e))
    ws = sh.get_worksheet(0)
    all_values = ws.get_all_values()
    header = all_values[0] if len(all_values) >= 1 else []
    rows = all_values[1:] if len(all_values) >= 2 else []
    return ws, header, rows, sh

st.header("ابحث بالباركود أو باسم المنتج")

col1, col2 = st.columns(2)
with col1:
    barcode_input = st.text_input("باركود (مطابق 100%)")
with col2:
    name_input = st.text_input("اسم المنتج (بحث جزئي)")

if st.button("بحث"):
    if (not barcode_input or not barcode_input.strip()) and (not name_input or not name_input.strip()):
        st.info("الرجاء إدخال باركود أو اسم المنتج ثم اضغط بحث.")
    else:
        try:
            ws, header, rows, sh = open_products_sheet()
            q_barcode = barcode_input.strip()
            q_name = name_input.strip().lower()

            # افتراض: العمود A = باركود (index 0)، العمود B = اسم المنتج (index 1)
            BARCODE_IDX = 0
            NAME_IDX = 1

            exact_barcode_matches = []
            name_matches = []

            for idx, row in enumerate(rows, start=2):  # start=2 لأننا تجاهلنا رأس العمود
                cell_barcode = row[BARCODE_IDX] if len(row) > BARCODE_IDX else ""
                cell_name = row[NAME_IDX] if len(row) > NAME_IDX else ""
                # باركود: مطابقة 100%
                if q_barcode and cell_barcode and q_barcode == cell_barcode:
                    exact_barcode_matches.append((idx, row))
                # اسم: تطابق جزئي غير حساس لحالة الأحرف
                if q_name and cell_name and q_name in cell_name.lower():
                    name_matches.append((idx, row))

            # عرض النتائج حسب الأولوية: باركود أولاً
            if exact_barcode_matches:
                st.success(f"تم العثور على {len(exact_barcode_matches)} نتيجة مطابقة للباركود (مطابقة 100%).")
                for r_idx, r in exact_barcode_matches:
                    st.markdown(f"**صف {r_idx}**")
                    display = {}
                    for col_i, cell in enumerate(r, start=1):
                        col_name = header[col_i-1] if len(header) >= col_i else f"عمود {col_i}"
                        display[col_name] = cell
                    st.table([display])
            elif name_matches:
                st.success(f"تم العثور على {len(name_matches)} نتيجة تطابق بالاسم.")
                options = []
                for r_idx, r in name_matches:
                    nm = r[NAME_IDX] if len(r) > NAME_IDX else "(بدون اسم)"
                    bc = r[BARCODE_IDX] if len(r) > BARCODE_IDX else ""
                    options.append(f"صف {r_idx} - {nm} - باركود: {bc}")
                choice = st.selectbox("اختر المنتج لعرض التفاصيل:", options)
                if choice:
                    try:
                        chosen_row_idx = int(choice.split("-")[0].strip().split()[1])
                        row_values = ws.row_values(chosen_row_idx)
                        display = {}
                        for col_i, cell in enumerate(row_values, start=1):
                            col_name = header[col_i-1] if len(header) >= col_i else f"عمود {col_i}"
                            display[col_name] = cell
                        st.markdown(f"**تفاصيل المنتج في صف {chosen_row_idx}:**")
                        st.table([display])
                    except Exception as ex:
                        st.error("حدث خطأ أثناء عرض تفاصيل المنتج: " + str(ex))
            else:
                st.info("لم يتم العثور على نتائج مطابقة.")
        except RuntimeError as re:
            # رسائل واضحة للمستخدم حول المصادقة أو فتح الشيت
            st.error("حدث خطأ أثناء الاتصال بالشيت أو أثناء البحث: " + str(re))
            # نصيحة سريعة للمستخدم
            st.info("تأكد أن: 1) تم تمكين Google Sheets API في مشروع Google Cloud، 2) تمت مشاركة الشيت مع عنوان البريد الخاص بالحساب الخدمي (client_email)، 3) القيم في Streamlit Secrets صحيحة.")
        except Exception as e:
            st.error("حدث خطأ غير متوقع: " + str(e))
