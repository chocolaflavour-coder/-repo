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

# ملاحظة: لا نعدّل private_key هنا إطلاقًا. Streamlit secrets يجب أن يحتوي على المفتاح كسطر واحد
# مع رموز \n داخل النص، وليس كسطور متعددة.

def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds_dict = None
    try:
        # 1) دعم وجود قسم كامل gcp_service_account في secrets (كـ dict)
        if "gcp_service_account" in st.secrets:
            creds_dict = st.secrets["gcp_service_account"]

        # 2) دعم وجود JSON كامل كنص في مفتاح service_account_json
        elif "service_account_json" in st.secrets:
            try:
                creds_dict = json.loads(st.secrets["service_account_json"])
            except Exception as e:
                creds_dict = None
                st.warning("تعذّر تحليل service_account_json من Streamlit secrets.")

        # 3) دعم الشكل التقليدي: مفاتيح منفصلة في st.secrets (type == service_account)
        elif "type" in st.secrets and st.secrets["type"] == "service_account":
            creds_dict = dict(st.secrets)

        # 4) دعم وجود المفاتيح الأساسية منفردة في secrets
        elif all(key in st.secrets for key in [
            "type", "project_id", "private_key", "client_email",
            "auth_uri", "token_uri", "auth_provider_x509_cert_url",
            "client_x509_cert_url"
        ]):
            creds_dict = dict(st.secrets)

    except StreamlitSecretNotFoundError:
        creds_dict = None

    # إذا حصلنا على بيانات اعتماد من secrets، نستخدمها مباشرة بدون أي تعديل على private_key
    if creds_dict is not None:
        try:
            credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            return gspread.authorize(credentials)
        except Exception as e:
            st.warning(
                "تعذّر استخدام بيانات الاعتماد من Streamlit secrets. "
                "تأكد أن القيم في secrets صحيحة وأن PRIVATE_KEY محفوظ كسطر واحد مع \\n داخل النص."
            )
            st.write(f"تفاصيل الخطأ: {e}")

    # محاولة قراءة من متغيرات البيئة (SERVICE_ACCOUNT_JSON أو GOOGLE_SERVICE_ACCOUNT_JSON)
    env_json = os.environ.get("SERVICE_ACCOUNT_JSON") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if env_json:
        try:
            creds_dict = json.loads(env_json)
            credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            return gspread.authorize(credentials)
        except Exception as e:
            st.warning(
                "تعذّر استخدام بيانات الاعتماد من متغير البيئة SERVICE_ACCOUNT_JSON."
            )
            st.write(f"الخطأ: {e}")

    # محاولة العثور على ملفات محلية (للتشغيل المحلي)
    try:
