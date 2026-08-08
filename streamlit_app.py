import os
import json
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit.errors import StreamlitSecretNotFoundError
# save as check_syntax.py ثم شغّل: python check_syntax.py
# save as check_syntax.py ثم شغّل: python check_syntax.py
import ast, sys

fname = "streamlit_app.py"
with open(fname, "r", encoding="utf-8") as f:
    src = f.read()

try:
    ast.parse(src)
    print("لا توجد أخطاء نحوية (AST parse ناجح).")
except SyntaxError as e:
    print("SyntaxError:", e)
    lineno = e.lineno or 0
    start = max(1, lineno-6)
    end = lineno+6
    lines = src.splitlines()
    print(f"\nعرض الأسطر من {start} إلى {end}:")
    for i in range(start, min(end, len(lines))+1):
        prefix = ">>" if i==lineno else "  "
        print(f"{prefix} {i:03d}: {lines[i-1]}")
    sys.exit(1)


# ----------------- إعداد الصفحة -----------------
st.set_page_config(page_title="🧪 إدارة تحديثات المنتجات من Google Sheets", layout="wide")
st.title("🧪 إدارة تحديثات المنتجات من Google Sheets")

# ----------------- إعدادات الورقة -----------------
SPREADSHEET_ID = "1MOuwq51Y-Odvn9F7k4C5IVkGBDfPlS-HBUh7fVw6Rok"
PRODUCT_SHEET = "المنتجات"
UPDATES_SHEET = "التحديثات"

st.write(
    "هذا التطبيق يبحث في ورقة `المنتجات` حسب الباركود أو اسم المنتج، "
    "ثم يطلب تاريخ انتهاء صلاحية والكمية ويضيف صفًا جديدًا إلى ورقة `التحديثات`."
)

# ----------------- دالة الحصول على عميل gspread -----------------
def get_gspread_client(debug: bool = False):
    """
    استراتيجية آمنة ومرنة لتحميل بيانات اعتماد Google:
    1) جرب st.secrets أولاً (مناسب لـ Streamlit Cloud).
    2) ثم جرب متغيرات البيئة (SERVICE_ACCOUNT_JSON أو GOOGLE_SERVICE_ACCOUNT_JSON).
    3) ثم جرب ملفات JSON محلية (key.json, service_account.json, credentials.json).
    لا نغيّر قيمة private_key في الكود إطلاقًا — نمرّر dict كما هو.
    """
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # --- 1) محاولة من st.secrets ---
    try:
        creds_dict = None
        if "gcp_service_account" in st.secrets:
            creds_dict = st.secrets["gcp_service_account"]
            if debug:
                st.info("استخدام st.secrets['gcp_service_account']")
        elif "service_account_json" in st.secrets:
            try:
                creds_dict = json.loads(st.secrets["service_account_json"])
                if debug:
                    st.info("استخدام st.secrets['service_account_json'] (JSON)")
            except Exception:
                creds_dict = None
                if debug:
                    st.warning("service_account_json موجود لكن لا يمكن تحليله كـ JSON")
        elif "type" in st.secrets and st.secrets["type"] == "service_account":
            creds_dict = dict(st.secrets)
            if debug:
                st.info("استخدام st.secrets كمفاتيح منفصلة (type == service_account)")
        elif all(key in st.secrets for key in [
            "type", "project_id", "private_key", "client_email",
            "auth_uri", "token_uri", "auth_provider_x509_cert_url",
            "client_x509_cert_url"
        ]):
            creds_dict = dict(st.secrets)
            if debug:
                st.info("استخدام st.secrets (مفاتيح أساسية متفرقة)")

        if creds_dict is not None:
            try:
                credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                if debug:
                    st.success("نجح التفويض باستخدام st.secrets")
                return gspread.authorize(credentials)
            except Exception as e:
                if debug:
                    st.error("فشل التفويض باستخدام st.secrets")
                    st.code(str(e))
                # لا نعيد رفع الاستثناء هنا، ننتقل للمصادر التالية
    except StreamlitSecretNotFoundError:
        if debug:
            st.info("st.secrets غير متوفرة في هذا السياق")

    # --- 2) محاولة من متغيرات البيئة ---
    env_json = os.environ.get("SERVICE_ACCOUNT_JSON") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if env_json:
        try:
            creds_dict = json.loads(env_json)
            credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            if debug:
                st.success("نجح التفويض باستخدام متغير البيئة SERVICE_ACCOUNT_JSON")
            return gspread.authorize(credentials)
        except Exception as e:
            if debug:
                st.error("فشل التفويض باستخدام متغير البيئة SERVICE_ACCOUNT_JSON")
                st.code(str(e))

    # --- 3) محاولة من ملفات محلية (مفيد للتشغيل المحلي) ---
    try:
        project_dir = Path(__file__).resolve().parent
    except Exception:
        project_dir = Path.cwd()

    local_candidates = [
        project_dir / "key.json",
        project_dir / "service_account.json",
        project_dir / "credentials.json",
    ]

    for p in local_candidates:
        if p.exists():
            try:
                if debug:
                    st.info(f"محاولة التفويض من الملف المحلي: {p.name}")
                return gspread.service_account(filename=str(p), scopes=scopes)
            except Exception as e:
                if debug:
                    st.error(f"فشل استخدام الملف المحلي {p.name}")
                    st.code(str(e))
                # تابع المحاولة مع الملفات الأخرى

    # --- فشل العثور على بيانات اعتماد ---
    if debug:
        st.error(
            "لم تُوجد بيانات اعتماد صالحة. على Streamlit Cloud: أضف JSON حساب الخدمة عبر Secrets "
            "(gcp_service_account أو service_account_json أو مفاتيح منفصلة)."
        )
    return None

# ----------------- دوال مساعدة للتعامل مع الورقة -----------------
def load_sheet_dataframe(worksheet):
    records = worksheet.get_all_records()
    return pd.DataFrame(records)

def append_update_row(worksheet, row_values):
    worksheet.append_row(row_values, value_input_option="USER_ENTERED")

# ----------------- خيار تشغيل الفحص التشخيصي مؤقتًا -----------------
DEBUG_MODE = st.sidebar.checkbox("تشغيل وضع التشخيص (عرض تفاصيل الاتصال)", value=False)

# ----------------- تنفيذ الاتصال وواجهة المستخدم -----------------
client = get_gspread_client(debug=DEBUG_MODE)
if client is not None:
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        product_ws = spreadsheet.worksheet(PRODUCT_SHEET)
        updates_ws = spreadsheet.worksheet(UPDATES_SHEET)

        df_products = load_sheet_dataframe(product_ws)
        if df_products.empty:
            st.warning("ورقة المنتجات فارغة أو لا تحتوي على بيانات.")
        else:
            headers = list(df_products.columns)
            if len(headers) < 2:
                st.error("ورقة المنتجات يجب أن تحتوي على عمود باركود وعمود اسم المنتج على الأقل.")
            else:
                barcode_col = headers[0]
                product_col = headers[1]

                st.write("### ابحث عن منتج في ورقة المنتجات")
                st.write(f"عمود الباركود: `{barcode_col}`، عمود اسم المنتج: `{product_col}`")

                barcode_input = st.text_input("ادخل الباركود بدقة (مطابق 100%)")
                product_input = st.text_input("اكتب اسم المنتج جزئيًا لعرض النتائج")

                search_df = df_products
                if barcode_input:
                    search_df = search_df[search_df[barcode_col].astype(str).eq(barcode_input)]
                if product_input:
                    search_df = search_df[search_df[product_col].astype(str).str.contains(product_input, case=False, na=False)]

                if not barcode_input and not product_input:
                    st.info("ابدأ بكتابة الباركود أو اسم المنتج للبحث مباشرة.")
                    st.session_state.pop("search_results", None)
                    st.session_state.pop("found_product", None)
                else:
                    if search_df.empty:
                        st.info("لم يتم العثور على نتائج. حاول تعديل البحث.")
                        st.session_state.pop("search_results", None)
                        st.session_state.pop("found_product", None)
                    elif len(search_df) == 1:
                        product_row = search_df.iloc[0]
                        st.session_state["found_product"] = product_row.to_dict()
                        st.session_state.pop("search_results", None)
                        st.success("تم العثور على المنتج.")
                    else:
                        st.session_state["search_results"] = search_df.to_dict("records")
                        st.session_state.pop("found_product", None)

                if "search_results" in st.session_state:
                    choices = [f"{row[barcode_col]} - {row[product_col]}" for row in st.session_state["search_results"]]
                    selected_choice = st.selectbox("النتائج المتطابقة، اختر المنتج المطلوب", choices)
                    selected_index = choices.index(selected_choice)
                    selected_row = st.session_state["search_results"][selected_index]
                    st.session_state["found_product"] = selected_row
                    st.success("تم اختيار المنتج من النتائج.")

                if "found_product" in st.session_state:
                    product_row = st.session_state["found_product"]
                    st.write("### بيانات المنتج")
                    st.write(product_row)

                    with st.form("update_form"):
                        expiry_date = st.date_input("تاريخ الانتهاء")
                        quantity = st.number_input("الكمية", min_value=0, step=1)
                        submit_update = st.form_submit_button("حفظ التحديث")

                    if submit_update:
                        update_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        update_row = [
                            str(product_row[barcode_col]),
                            str(product_row[product_col]),
                            expiry_date.isoformat(),
                            int(quantity),
                            update_datetime,
                        ]
                        append_update_row(updates_ws, update_row)
                        st.success("تم حفظ التحديث في ورقة التحديثات.")
                        st.write(update_row)
                        st.session_state.pop("found_product", None)
    except Exception as e:
        st.error(f"حدث خطأ أثناء الاتصال بـ Google Sheets: {e}")
else:
    st.error(
        "لم يتمكن التطبيق من إنشاء اتصال بـ Google Sheets. "
        "تأكد من إعداد Streamlit Secrets أو وجود ملف JSON محلي صالح."
    )

# ----------------- ملاحظات سريعة للمستخدم -----------------
st.markdown("---")
st.markdown(
    """
    **ملاحظات مهمة**
    - على Streamlit Cloud: ضع بيانات اعتماد حساب الخدمة في Settings → Secrets.
    - تأكد أن `PRIVATE_KEY` مخزّن كسطر واحد مع `\\n` داخل النص، مثال:
      `PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----\\nMIIC...==\\n-----END PRIVATE KEY-----\\n"`
    - لا تقم بتعديل قيمة `private_key` في الكود (لا تستخدم replace أو normalize).
    - بعد تعديل Secrets انتظر دقيقة ثم أعد تحميل التطبيق.
    """
)
