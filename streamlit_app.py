# streamlit_app.py
import streamlit as st
from google.oauth2 import service_account
import gspread
import base64
from google.auth.exceptions import GoogleAuthError
import re
from datetime import datetime, timezone, timedelta
import uuid

st.set_page_config(page_title="إدارة المنتجات - تحديث الصفوف", layout="centered")
st.title("بحث وتحديث المنتجات")

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

# -------------------- حالة الجلسة الافتراضية --------------------
if "chosen_row" not in st.session_state:
    st.session_state["chosen_row"] = None
if "sh_id" not in st.session_state:
    st.session_state["sh_id"] = None
if "last_update" not in st.session_state:
    st.session_state["last_update"] = None  # {"name":..., "expiry":..., "qty":...}

# -------------------- عرض ملخص التحديث السابق (إن وُجد) فوق البحث فقط --------------------
if st.session_state.get("last_update"):
    lu = st.session_state["last_update"]
    st.success("تم تحديث الإدخال بنجاح")
    st.write(f"**اسم المنتج:** {lu.get('name','')}")
    st.write(f"**تاريخ الصلاحية:** {lu.get('expiry','')}")
    st.write(f"**الكمية:** {lu.get('qty','')}")
    st.markdown("---")

# -------------------- واجهة البحث --------------------
st.header("ابحث بالباركود أو باسم المنتج")
col1, col2 = st.columns(2)
with col1:
    barcode_input = st.text_input("باركود (مطابق 100%)", key="search_barcode")
with col2:
    name_input = st.text_input("اسم المنتج (بحث جزئي)", key="search_name")

# زر البحث
if st.button("بحث"):
    st.session_state["chosen_row"] = None
    # لا نمسح last_update هنا تلقائياً؛ المستخدم يريد رؤية آخر تحديث حتى يبدأ بحث جديد
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

        # افتراضات الأعمدة في شيت المنتجات (A,B,C,D)
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

        # --- معالجة نتائج الباركود مع خريطة ثابتة للاختيارات ---
        if exact_barcode_matches:
            if len(exact_barcode_matches) == 1:
                chosen = exact_barcode_matches[0]
            else:
                options_map = {}
                options = []
                for r_idx, r in exact_barcode_matches:
                    nm = r[NAME_IDX] if len(r) > NAME_IDX else "(بدون اسم)"
                    bc = r[BARCODE_IDX] if len(r) > BARCODE_IDX else ""
                    label = f"صف {r_idx} - {nm} - باركود: {bc}"
                    options.append(label)
                    options_map[label] = r_idx
                # مفتاح فريد يعتمد على uuid لضمان عدم تداخل الحالة
                sel_key = f"select_barcode_{uuid.uuid4().hex}"
                sel = st.selectbox("اختر المنتج من النتائج المطابقة:", options, key=sel_key)
                if sel:
                    chosen_row_idx = options_map[sel]
                    chosen_row = ws.row_values(chosen_row_idx)
                    chosen = (chosen_row_idx, chosen_row)
        # --- معالجة نتائج الاسم مع خريطة ثابتة للاختيارات ---
        elif name_matches:
            if len(name_matches) == 1:
                chosen = name_matches[0]
            else:
                options_map = {}
                options = []
                for r_idx, r in name_matches:
                    nm = r[NAME_IDX] if len(r) > NAME_IDX else "(بدون اسم)"
                    bc = r[BARCODE_IDX] if len(r) > BARCODE_IDX else ""
                    label = f"صف {r_idx} - {nm} - باركود: {bc}"
                    options.append(label)
                    options_map[label] = r_idx
                sel_key = f"select_name_{uuid.uuid4().hex}"
                sel = st.selectbox("اختر المنتج من النتائج:", options, key=sel_key)
                if sel:
                    chosen_row_idx = options_map[sel]
                    chosen_row = ws.row_values(chosen_row_idx)
                    chosen = (chosen_row_idx, chosen_row)

        else:
            st.info("لم يتم العثور على نتائج مطابقة.")

        if chosen:
            st.session_state["chosen_row"] = chosen
            st.session_state["sh_id"] = sh.id
            st.success("تم العثور على المنتج — يمكنك الآن تحديثه أدناه")

# -------------------- عرض حقول التحديث (تظهر فقط بعد اختيار نتيجة) --------------------
if st.session_state.get("chosen_row"):
    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(st.session_state["sh_id"])
        ws = sh.get_worksheet(0)
    except Exception:
        try:
            gc, sh, ws, header, rows = open_products_sheet()
        except Exception as e:
            st.error("تعذر إعادة فتح شيت المنتجات: " + str(e))
            st.stop()

    row_idx, row_values = st.session_state["chosen_row"]
    BARCODE_IDX = 0
    NAME_IDX = 1
    EXPIRY_IDX = 2
    QTY_IDX = 3

    current_barcode_cell = row_values[BARCODE_IDX] if len(row_values) > BARCODE_IDX else ""
    current_name = row_values[NAME_IDX] if len(row_values) > NAME_IDX else ""
    current_expiry = row_values[EXPIRY_IDX] if len(row_values) > EXPIRY_IDX else ""
    current_qty = row_values[QTY_IDX] if len(row_values) > QTY_IDX else ""

    st.markdown("### تحديث سريع")
    cols = st.columns(3)
    with cols[0]:
        st.write("**المنتج**")
        st.write(current_name or "(بدون اسم)")
    with cols[1]:
        st.write("**الباركود**")
        st.write(current_barcode_cell or "(بدون باركود)")
    with cols[2]:
        st.write("**الصف**")
        st.write(row_idx)

    try:
        default_qty = int(current_qty) if str(current_qty).strip().isdigit() else 0
    except Exception:
        default_qty = 0

    new_qty = st.number_input("الكمية الجديدة", min_value=0, step=1, value=default_qty, key=f"qty_{row_idx}")
    new_expiry = st.date_input("تاريخ الصلاحية الجديد", value=datetime.today().date(), key=f"expiry_{row_idx}")

    if st.button("تطبيق التحديث الآن"):
        try:
            expiry_str = new_expiry.strftime("%Y-%m-%d")
            new_qty_str = str(new_qty)

            # تحديث الخلايا في نفس الصف
            ws.update_cell(row_idx, EXPIRY_IDX + 1, expiry_str)
            ws.update_cell(row_idx, QTY_IDX + 1, new_qty_str)

            # تسجيل التحديث في ورقة "التحديثات" داخل نفس الملف
            ws_updates = get_updates_sheet_in_same_spreadsheet(sh)
            # توقيت السعودية UTC+3
            sa_time = datetime.now(timezone(timedelta(hours=3)))
            update_time = sa_time.strftime("%Y-%m-%d %H:%M:%S")
            barcode_cell_value = current_barcode_cell or ws.cell(row_idx, BARCODE_IDX + 1).value or ""
            product_name_for_log = current_name
            new_update_row = [barcode_cell_value, product_name_for_log, expiry_str, new_qty_str, update_time]
            try:
                ws_updates.append_row(new_update_row, value_input_option="USER_ENTERED")
            except Exception:
                vals = ws_updates.get_all_values()
                next_index = len(vals) + 1
                ws_updates.insert_row(new_update_row, index=next_index)

            # احفظ ملخص التحديث في الجلسة لعرضه فوق البحث فقط
            st.session_state["last_update"] = {
                "name": product_name_for_log,
                "expiry": expiry_str,
                "qty": new_qty_str
            }

            # إعادة تهيئة الحالة لعرض صفحة البحث فقط (نمسح حقول التحديث)
            st.session_state["chosen_row"] = None
            if "sh_id" in st.session_state:
                del st.session_state["sh_id"]

            # لا نستدعي experimental_rerun؛ الواجهة ستعرض ملخص التحديث في أعلى الصفحة تلقائياً
            # (بما أن last_update تم تعيينه، سيظهر عند إعادة عرض الصفحة)
        except Exception as e:
            st.exception(e)
