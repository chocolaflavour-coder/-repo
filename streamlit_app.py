import os
import json
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit.errors import StreamlitSecretNotFoundError

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
    env_json = os.environ.get("SERVICE_ACCOUNT_JSON") or os.environ.get("GOOGLE_SERVICE_ACCOUNT
