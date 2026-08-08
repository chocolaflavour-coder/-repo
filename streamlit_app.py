import os
import json
from pathlib import Path
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit.errors import StreamlitSecretNotFoundError
from datetime import datetime

st.title("🧪 إدارة تحديثات المنتجات من Google Sheets")

SPREADSHEET_ID = "1MOuwq51Y-Odvn9F7k4C5IVkGBDfPlS-HBUh7fVw6Rok"
PRODUCT_SHEET = "المنتجات"
UPDATES_SHEET = "التحديثات"

st.write(
    "هذا التطبيق يبحث في ورقة `المنتجات` حسب الباركود أو اسم المنتج، "
    "ثم يطلب تاريخ انتهاء صلاحية والكمية ويضيف صفًا جديدًا إلى ورقة `التحديثات`."
)

# ملاحظة مهمة: لا تقم بتعديل private_key في الكود.
# في Streamlit Secrets يجب أن يكون PRIVATE_KEY كسطر واحد مع رموز \n داخل النص.

def get_gspread_client():
    """
    تعديل بسيط في أولوية مصادر بيانات الاعتماد:
    1) أولاً نحاول استخدام ملف محلي (key.json أو service_account.json) — هذا هو المصدر الذي ثبت نجاحه عندك.
    2) ثم نحاول استخدام st.secrets (gcp_service_account أو service_account_json أو مفاتيح منفصلة).
    3) ثم نحاول متغيرات البيئة.
    4) أخيراً نبحث عن ملفات محلية أخرى كاحتياط.
    لا نعدّل قيمة private_key أبداً في الكود.
    """
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # 1) محاولة استخدام ملف محلي معروف أولاً (نجح معك سابقاً)
    try:
        project_dir = Path(__file__).resolve().parent
    except Exception:
        project_dir = Path.cwd()

    local_candidates = [
        project_dir / 'key.json',
        project_dir / 'service_account.json',
        project_dir / 'credentials.json',
    ]

    for p in local_candidates:
        if p.exists():
            try:
                # gspread.service_account سيقرأ الملف JSON مباشرة ويعمل التفويض
                return gspread.service_account(filename=str(p), scopes=scopes)
            except Exception as e:
                # لو فشل ملف محلي، نعرض رسالة وننتقل للمصادر الأخرى
                st.warning(f"تم العثور على {p.name} لكن فشل تحميل بيانات الاعتماد منه. الخطأ: {e}")

    # 2) محاولة قراءة من st.secrets (بدون أي تعديل على private_key)
    creds_dict = None
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = st.secrets["gcp_service_account"]
        elif "service_account_json" in st.secrets:
            try:
                creds_dict = json.loads(st.secrets["service_account_json"])
            except Exception:
                creds_dict = None
        elif "type" in st.secrets and st.secrets["type"] == "service_account":
            creds_dict = dict(st.secrets)
        elif all(key in st.secrets for key in [
            "type", "project_id", "private_key", "client_email",
            "auth_uri", "token_uri", "auth_provider_x509_cert_url",
            "client_x509_cert_url"
        ]):
            creds_dict = dict(st.secrets)
    except StreamlitSecretNotFoundError:
        creds_dict = None

    if creds_dict is not None:
        try:
            credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            return gspread.authorize(credentials)
        except Exception as e:
            st.warning(
                "تعذّر استخدام بيانات الاعتماد من Streamlit secrets. "
                "تأكد أن PRIVATE_KEY محفوظ كسطر واحد مع \\n داخل النص."
            )
            st.write(f"تفاصيل الخطأ: {e}")

    # 3) محاولة قراءة من متغيرات البيئة (SERVICE_ACCOUNT_JSON أو GOOGLE_SERVICE_ACCOUNT_JSON)
    env_json = os.environ.get("SERVICE_ACCOUNT_JSON") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if env_json:
        try:
            creds_dict = json.loads(env_json)
            credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            return gspread.authorize(credentials)
        except Exception as e:
            st.warning(
                "تعذّر استخدام بيانات الاعتماد من متغير البيئة SERVICE_ACCOUNT_JSON. "
                f"الخطأ: {e}"
            )

    # 4) محاولة العثور على ملفات محلية إضافية (كاحتياط)
    possible_files = [
        project_dir / '.streamlit' / 'secrets.toml',
    ]

    for file_path in possible_files:
        if file_path.exists():
            # نتجنب محاولة تحميل ملف TOML كـ JSON
            if file_path.suffix == '.toml':
                continue
            try:
                return gspread.service_account(filename=str(file_path), scopes=scopes)
            except Exception as e:
                st.error(
                    f"تم العثور على {file_path.name} لكن فشل تحميل بيانات الاعتماد. "
                    f"الخطأ: {e}"
                )
                return None

    st.error(
        "لم تُوجد بيانات اعتماد Google Sheets. على Streamlit Cloud، أضف JSON حساب الخدمة عبر Secrets "
        "ضمن المفتاح gcp_service_account أو service_account_json. "
        "إذا كنت تشغّل محلياً، ضع ملف key.json أو service_account.json في مجلد المشروع."
    )
    return None


def load_sheet_dataframe(worksheet):
    records = worksheet.get_all_records()
    return pd.DataFrame(records)


def append_update_row(worksheet, row_values):
    worksheet.append_row(row_values, value_input_option="USER_ENTERED")


client = get_gspread_client()
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
