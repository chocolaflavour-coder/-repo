# streamlit_app.py
import streamlit as st
from google.oauth2 import service_account
import gspread
import base64
from google.auth.exceptions import GoogleAuthError
import re
from datetime import datetime

st.set_page_config(page_title="إدارة المنتجات - تحديث (اختبار التحديثات)", layout="centered")
st.title("بحث وتحديث المنتجات (مع زر اختبار لإضافة سجل في التحديثات)")

# -------------------- مفاتيح وتهيئة --------------------
def load_private_key():
    pk = st.secrets.get("PRIVATE_KEY")
    if pk:
        return pk
    pk_b64 = st.secrets.get("PRIVATE_KEY_B64")
    if pk_b64:
        return base64.b64decode(pk_b64).decode("utf-8")
    return None

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

def get_gspread_client():
    info = build_service_account_info()
    missing = [k for k, v in info.items() if not v]
    if missing:
        raise RuntimeError("متغيرات مفقودة في Secrets: " + ", ".join(missing))
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

# -------------------- فتح شيت المنتجات --------------------
def open_products_sheet():
    gc = get_gspread_client()
    try:
        sh = gc.open("المنتجات")
    except Exception as e:
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
    return gc, sh, ws, header, rows

# -------------------- فتح/إنشاء ورقة "التحديثات" داخل نفس الملف --------------------
def get_updates_sheet_in_same_spreadsheet(sh):
    try:
        ws_updates = sh.worksheet("التحديثات")
    except Exception:
        try:
            ws_updates = sh.add_worksheet(title="التحديثات", rows="2000", cols="10")
        except Exception as e:
            raise RuntimeError("تعذر إنشاء ورقة 'التحديثات' داخل ملف 'المنتجات': " + str(e))
    try:
        headers = ws_updates.row_values(1)
    except Exception:
        headers = []
    expected = ["الباركود", "اسم المنتج", "تاريخ الصلاحية", "الكمية", "وقت التحديث"]
    if headers[:len(expected)] != expected:
        try:
            if headers:
                ws_updates.delete_rows(1)
        except Exception:
            pass
        try:
            ws_updates.insert_row(expected, index=1)
        except Exception as e:
            raise RuntimeError("تعذر إدراج رؤوس الأعمدة في ورقة 'التحديثات': " + str(e))
    return ws_updates

# -------------------- مساعدة تقسيم الباركودات --------------------
def split_barcodes(cell_text):
    if not cell_text:
        return []
    cleaned = re.sub(r"[,;|]+", " ", cell_text)
    parts = re.split(r"\s+", cleaned.strip())
    return [p for p in parts if p]

# -------------------- زر اختبار: إضافة سجل تجريبي في ورقة "التحديثات" داخل نفس ملف "المنتجات" --------------------
st.markdown("### اختبار سريع: إضافة سجل تجريبي في ورقة التحديثات")
st.write("هذا الاختبار سيحاول فتح ملف 'المنتجات' ثم إضافة صف تجريبي في ورقة 'التحديثات' داخل نفس الملف.")
if st.button("اختبار إضافة سجل في التحديثات"):
    try:
        gc, sh, ws, header, rows = open_products_sheet()
    except Exception as e:
        st.error("فشل الاتصال بشيت 'المنتجات': " + str(e))
        st.stop()
    try:
        ws_updates = get_updates_sheet_in_same_spreadsheet(sh)
    except Exception as e:
        st.error("فشل الحصول على ورقة 'التحديثات' داخل نفس الملف: " + str(e))
        st.exception(e)
        st.stop()

    # صف تجريبي
    test_barcode = "TEST-UPDATE-001"
    test_name = "TEST-PRODUCT-UPDATE"
    test_expiry = "2099-12-31"
    test_qty = "1"
    test_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    test_row = [test_barcode, test_name, test_expiry, test_qty, test_time]

    st.write("سأحاول إضافة الصف التالي إلى ورقة 'التحديثات':", test_row)
    try:
        ws_updates.append_row(test_row, value_input_option="USER_ENTERED")
        st.success("نجح: تم إضافة السجل التجريبي إلى ورقة 'التحديثات' داخل ملف 'المنتجات'.")
        # عرض معلومات تشخيصية
        try:
            vals = ws_updates.get_all_values()
            st.write("عدد الصفوف الآن في 'التحديثات':", len(vals))
            st.write("آخر صف في 'التحديثات':", vals[-1])
        except Exception as e:
            st.warning("تمت الإضافة لكن تعذر قراءة محتوى ورقة 'التحديثات': " + str(e))
    except Exception as e:
        st.error("فشل append_row على ورقة 'التحديثات': " + str(e))
        st.exception(e)
        # محاولة إدراج يدويًا في الصف التالي
        try:
            vals = ws_updates.get_all_values()
            next_index = len(vals) + 1
            ws_updates.insert_row(test_row, index=next_index)
            st.success(f"نجح: تم إدراج السجل التجريبي في ورقة 'التحديثات' في الصف {next_index}.")
        except Exception as e2:
            st.error("فشل إدراج السجل التجريبي أيضاً.")
            st.exception(e2)

st.markdown("---")

# -------------------- واجهة البحث والتحديث (كما في النسخة السابقة) --------------------
st.header("ابحث بالباركود أو باسم المنتج")

col1, col2 = st.columns(2)
with col1:
    barcode_input = st.text_input("باركود (مطابق 100%)")
with col2:
    name_input = st.text_input("اسم المنتج (بحث جزئي)")

# زر البحث
if st.button("بحث"):
    if (not barcode_input or not barcode_input.strip()) and (not name_input or not name_input.strip()):
        st.info("الرجاء إدخال باركود أو اسم المنتج ثم اضغط بحث.")
    else:
        try:
            gc, sh, ws, header, rows = open_products_sheet()
        except Exception as e:
            st.error("فشل الاتصال بشيت المنتجات: " + str(e))
            st.stop()

        q_barcode = barcode_input.strip()
        q_name = name_input.strip().lower()

        BARCODE_IDX = 0
        NAME_IDX = 1
        EXPIRY_IDX = 2
        QTY_IDX = 3

        exact_barcode_matches = []
        name_matches = []

        for idx, row in enumerate(rows, start=2):
            cell_barcode = row[BARCODE_IDX] if len(row) > BARCODE_IDX else ""
            cell_name = row[NAME_IDX] if len(row) > NAME_IDX else ""
            if q_barcode and cell_barcode:
                parts = split_barcodes(cell_barcode)
                for part in parts:
                    if q_barcode == part:
                        exact_barcode_matches.append((idx, row))
                        break
            if q_name and cell_name and q_name in cell_name.lower():
                name_matches.append((idx, row))

        chosen = None

        if exact_barcode_matches:
            st.success(f"تم العثور على {len(exact_barcode_matches)} نتيجة مطابقة للباركود.")
            if len(exact_barcode_matches) == 1:
                chosen = exact_barcode_matches[0]
                st.markdown(f"**المنتج المختار: صف {chosen[0]}**")
                display = {}
                for col_i, cell in enumerate(chosen[1], start=1):
                    col_name = header[col_i-1] if len(header) >= col_i else f"عمود {col_i}"
                    display[col_name] = cell
                st.table([display])
            else:
                options = []
                for r_idx, r in exact_barcode_matches:
                    nm = r[NAME_IDX] if len(r) > NAME_IDX else "(بدون اسم)"
                    bc = r[BARCODE_IDX] if len(r) > BARCODE_IDX else ""
                    options.append(f"صف {r_idx} - {nm} - باركود: {bc}")
                choice = st.selectbox("اختر المنتج من النتائج المطابقة:", options)
                if choice:
                    chosen_row_idx = int(choice.split("-")[0].strip().split()[1])
                    chosen_row = ws.row_values(chosen_row_idx)
                    chosen = (chosen_row_idx, chosen_row)
        elif name_matches:
            st.success(f"تم العثور على {len(name_matches)} نتيجة تطابق بالاسم.")
            options = []
            for r_idx, r in name_matches:
                nm = r[NAME_IDX] if len(r) > NAME_IDX else "(بدون اسم)"
                bc = r[BARCODE_IDX] if len(r) > BARCODE_IDX else ""
                options.append(f"صف {r_idx} - {nm} - باركود: {bc}")
            choice = st.selectbox("اختر المنتج من النتائج:", options)
            if choice:
                chosen_row_idx = int(choice.split("-")[0].strip().split()[1])
                chosen_row = ws.row_values(chosen_row_idx)
                chosen = (chosen_row_idx, chosen_row)
        else:
            st.info("لم يتم العثور على نتائج مطابقة.")

        if chosen:
            row_idx, row_values = chosen
            current_barcode_cell = row_values[BARCODE_IDX] if len(row_values) > BARCODE_IDX else ""
            current_name = row_values[NAME_IDX] if len(row_values) > NAME_IDX else ""
            current_expiry = row_values[EXPIRY_IDX] if len(row_values) > EXPIRY_IDX else ""
            current_qty = row_values[QTY_IDX] if len(row_values) > QTY_IDX else ""

            st.markdown("### تحديث الكمية وتاريخ الصلاحية (إضافة صف جديد في 'المنتجات' + تسجيل في ورقة 'التحديثات')")
            with st.form("update_product_form"):
                try:
                    default_qty = int(current_qty) if str(current_qty).strip().isdigit() else 0
                except Exception:
                    default_qty = 0
                new_qty = st.number_input("الكمية الجديدة", min_value=0, step=1, value=default_qty)
                new_expiry = st.date_input("تاريخ الصلاحية (اختر التاريخ)", value=datetime.today().date())
                submit_update = st.form_submit_button("تطبيق التحديث (إضافة صف جديد)")

                if submit_update:
                    try:
                        expiry_str = new_expiry.strftime("%Y-%m-%d")
                        new_qty_str = str(new_qty)
                        st.info(f"محاولة إضافة صف جديد في شيت 'المنتجات' -> تاريخ: {expiry_str}، كمية: {new_qty_str}")

                        # أضف صفًا جديدًا في شيت المنتجات
                        barcode_cell_value = current_barcode_cell or ""
                        new_product_row = [barcode_cell_value, current_name, expiry_str, new_qty_str]
                        try:
                            ws.append_row(new_product_row, value_input_option="USER_ENTERED")
                            st.success("تم إضافة صف جديد في شيت 'المنتجات'.")
                        except Exception as e:
                            st.error("فشل إضافة صف جديد في شيت 'المنتجات': " + str(e))
                            raise

                        # تسجيل في ورقة التحديثات داخل نفس الملف (مع تشخيص)
                        try:
                            ws_updates = get_updates_sheet_in_same_spreadsheet(sh)
                            update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            new_update_row = [barcode_cell_value, current_name, expiry_str, new_qty_str, update_time]
                            st.write("الصف الذي سأحاول إضافته إلى 'التحديثات':", new_update_row)
                            try:
                                ws_updates.append_row(new_update_row, value_input_option="USER_ENTERED")
                                st.success("نجح: تم إضافة السجل في ورقة 'التحديثات'.")
                            except Exception as e_append:
                                st.warning("فشل append_row على ورقة 'التحديثات': " + str(e_append))
                                try:
                                    vals = ws_updates.get_all_values()
                                    next_index = len(vals) + 1
                                    ws_updates.insert_row(new_update_row, index=next_index)
                                    st.success(f"نجح: تم إدراج السجل في ورقة 'التحديثات' في الصف {next_index}.")
                                except Exception as e_insert:
                                    st.error("فشل إدراج السجل في ورقة 'التحديثات' أيضاً.")
                                    st.exception(e_insert)
                        except Exception as e_updates:
                            st.error("حدث خطأ أثناء محاولة تسجيل السجل في ورقة 'التحديثات'.")
                            st.exception(e_updates)

                        # عرض آخر صف في المنتجات للتأكيد
                        try:
                            all_vals_after = ws.get_all_values()
                            last_row = all_vals_after[-1] if all_vals_after else []
                            st.write("آخر صف في 'المنتجات' بعد الإضافة:", last_row)
                        except Exception as e:
                            st.warning("تعذر قراءة آخر صف بعد الإضافة: " + str(e))

                    except Exception as e:
                        st.exception(e)
