import os
import json
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.title("🧪 إدارة تحديثات المنتجات من Google Sheets")

SPREADSHEET_ID = "1MOuwq51Y-Odvn9F7k4C5IVkGBDfPlS-HBUh7fVw6Rok"
PRODUCT_SHEET = "المنتجات"
UPDATES_SHEET = "التحديثات"

st.write(
    "هذا التطبيق يبحث في ورقة `المنتجات` حسب الباركود أو اسم المنتج، "
    "ثم يطلب تاريخ انتهاء صلاحية والكمية ويضيف صفًا جديدًا إلى ورقة `التحديثات`."
)


def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds_dict = None
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
    elif "type" in st.secrets and st.secrets["type"] == "service_account":
        creds_dict = dict(st.secrets)

    if creds_dict is not None:
        try:
            credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            return gspread.authorize(credentials)
        except Exception:
            pass

    service_account_path = os.path.join('.', 'service_account.json')
    if os.path.exists(service_account_path):
        try:
            return gspread.service_account(filename=service_account_path, scopes=scopes)
        except Exception as e:
            st.error(
                "تم العثور على service_account.json لكن فشل تحميل بيانات الاعتماد. "
                f"الخطأ: {e}"
            )
            return None

    st.error(
        "يرجى إضافة بيانات حساب الخدمة إلى .streamlit/secrets.toml تحت gcp_service_account "
        "أو وضع ملف JSON الخاص بحساب الخدمة باسم service_account.json في مجلد المشروع."
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
