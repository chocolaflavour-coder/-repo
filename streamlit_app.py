import os
import json
import traceback
import streamlit as st
from pathlib import Path
from google.oauth2.service_account import Credentials
import gspread

st.markdown("## Debug اتصال Google Sheets")

# 1) عرض مفاتيح st.secrets
st.write("**مفاتيح st.secrets المتوفرة:**", list(st.secrets.keys()))

# 2) فحص PRIVATE_KEY إن وجد
if "PRIVATE_KEY" in st.secrets:
    pk = st.secrets["PRIVATE_KEY"]
    st.write("**نوع PRIVATE_KEY:**", type(pk).__name__)
    st.write("**طول PRIVATE_KEY:**", len(pk))
    st.code(repr(pk)[:1000])
    st.write("**يبدأ بـ BEGIN:**", pk.strip().startswith("-----BEGIN PRIVATE KEY-----"))
    st.write("**ينتهي بـ END:**", pk.strip().endswith("-----END PRIVATE KEY-----"))
else:
    st.write("**PRIVATE_KEY غير موجود في st.secrets**")

# دالة مساعدة لتجربة إنشاء عميل gspread من dict
def try_from_dict(name, creds_dict):
    st.write(f"---\n**محاولة إنشاء Credentials من {name}**")
    try:
        creds = Credentials.from_service_account_info(creds_dict)
        client = gspread.authorize(creds)
        st.success(f"نجح الاتصال باستخدام {name}")
        return True
    except Exception as e:
        st.error(f"فشل الاتصال باستخدام {name}")
        st.write("خطأ مفصّل:")
        st.code(traceback.format_exc())
        return False

# 3) تجربة من st.secrets كـ dict (إن كانت مفاتيح منفصلة أو قسم gcp_service_account)
if "gcp_service_account" in st.secrets:
    try_from_dict("st.secrets['gcp_service_account']", dict(st.secrets["gcp_service_account"]))
elif "service_account_json" in st.secrets:
    try:
        parsed = json.loads(st.secrets["service_account_json"])
        try_from_dict("st.secrets['service_account_json']", parsed)
    except Exception:
        st.warning("service_account_json موجود لكن لا يمكن تحليله كـ JSON.")
elif "type" in st.secrets and st.secrets["type"] == "service_account":
    try_from_dict("st.secrets (keys منفصلة)", dict(st.secrets))
elif all(k in st.secrets for k in ["type","project_id","private_key","client_email"]):
    try_from_dict("st.secrets (مفاتيح أساسية)", dict(st.secrets))
else:
    st.info("لم يتم العثور على بيانات اعتماد مناسبة داخل st.secrets لاختبارها.")

# 4) تجربة من متغير البيئة
env_json = os.environ.get("SERVICE_ACCOUNT_JSON") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
if env_json:
    st.write("---\n**محاولة من متغير البيئة SERVICE_ACCOUNT_JSON**")
    try:
        parsed = json.loads(env_json)
        try_from_dict("ENV SERVICE_ACCOUNT_JSON", parsed)
    except Exception:
        st.error("متغير البيئة موجود لكن لا يمكن تحليله كـ JSON.")
        st.code(traceback.format_exc())

# 5) تجربة من ملف محلي شائع
st.write("---\n**محاولة العثور على ملف محلي**")
try:
    project_dir = Path(__file__).resolve().parent
except Exception:
    project_dir = Path.cwd()

candidates = [project_dir / 'service_account.json', project_dir / 'key.json', project_dir / 'credentials.json']
found = False
for p in candidates:
    if p.exists():
        found = True
        st.write(f"تم العثور على ملف: {p}")
        try:
            creds = json.loads(p.read_text(encoding='utf-8'))
            try_from_dict(f"file {p.name}", creds)
        except Exception:
            st.error(f"فشل قراءة أو استخدام {p.name}")
            st.code(traceback.format_exc())

if not found:
    st.info("لم يتم العثور على ملفات JSON محلية من القائمة الافتراضية.")
