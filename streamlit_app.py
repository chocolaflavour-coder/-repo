# ملف تشخيصي كامل لاختبار اتصال Google Sheets تدريجياً على Streamlit
# انسخ هذا الملف كاملًا والصقه مكان ملف التطبيق مؤقتًا ثم شغّله.
# لا يغيّر أي secret داخل الكود. هذا ملف تشخيصي فقط.

import os
import json
import traceback
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit.errors import StreamlitSecretNotFoundError

st.set_page_config(page_title="Debug اتصال Google Sheets", layout="wide")
st.title("🔍 فحوصات تشخيصية اتصال Google Sheets (تدريجي)")

st.markdown(
    """
    **تعليمات سريعة**
    - هذا الملف مخصّص للتشخيص فقط. انسخه كما هو وأعد تشغيل التطبيق.
    - لا تضع أو تعرض المفتاح الكامل هنا للعامة. النتائج تعرض `repr` مقتطع للمفتاح فقط.
    - استخدم الأزرار لتشغيل كل اختبار على حدة أو تشغيل الكل خطوة بخطوة.
    """
)

# ---------- إعدادات عامة ----------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# مسارات ملفات محلية محتملة (الترتيب مهم لاختبار الأولويات)
try:
    PROJECT_DIR = Path(__file__).resolve().parent
except Exception:
    PROJECT_DIR = Path.cwd()

LOCAL_CANDIDATES = [
    PROJECT_DIR / "key.json",
    PROJECT_DIR / "service_account.json",
    PROJECT_DIR / "credentials.json",
]

# ---------- واجهة المستخدم ----------
st.sidebar.header("خيارات الاختبار")
force_use = st.sidebar.selectbox(
    "إجبار مصدر بيانات الاعتماد (اختياري)",
    options=["لا تجبر", "استخدم ملف محلي أولاً", "استخدم st.secrets أولاً", "استخدم متغير البيئة أولاً"]
)

run_all = st.sidebar.button("تشغيل كل الاختبارات بالتسلسل")
run_local_btn = st.sidebar.button("اختبار ملف محلي")
run_secrets_btn = st.sidebar.button("اختبار st.secrets")
run_env_btn = st.sidebar.button("اختبار متغير البيئة")
run_auth_btn = st.sidebar.button("محاولة تفويض gspread (authorize)")

st.markdown("---")

# ---------- أدوات مساعدة ----------
def short_repr(s: str, max_chars: int = 400):
    r = repr(s)
    return r[:max_chars] + ("..." if len(r) > max_chars else "")

def try_from_dict(name: str, creds_dict: dict, show_trace: bool = True):
    st.write(f"### محاولة إنشاء Credentials من: **{name}**")
    try:
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        st.success(f"✅ نجح الاتصال باستخدام {name}")
        return True, None
    except Exception as e:
        st.error(f"❌ فشل الاتصال باستخدام {name}")
        if show_trace:
            st.code(traceback.format_exc())
        return False, e

# ---------- فحص st.secrets ----------
def inspect_secrets():
    st.subheader("1) فحص st.secrets")
    keys = list(st.secrets.keys())
    st.write("مفاتيح st.secrets المتوفرة:", keys)

    if "PRIVATE_KEY" in st.secrets:
        pk = st.secrets["PRIVATE_KEY"]
        st.write("نوع PRIVATE_KEY:", type(pk).__name__)
        st.write("طول PRIVATE_KEY:", len(pk))
        st.code(short_repr(pk, 800))
        st.write("يبدأ بـ BEGIN:", pk.strip().startswith("-----BEGIN PRIVATE KEY-----"))
        st.write("ينتهي بـ END:", pk.strip().endswith("-----END PRIVATE KEY-----"))
    else:
        st.info("PRIVATE_KEY غير موجود في st.secrets")

    # دعم أقسام مختلفة
    if "gcp_service_account" in st.secrets:
        st.write("- يوجد قسم `gcp_service_account` في st.secrets.")
    if "service_account_json" in st.secrets:
        st.write("- يوجد مفتاح `service_account_json` في st.secrets (نص JSON).")

# ---------- اختبار ملف محلي ----------
def test_local_files():
    st.subheader("2) اختبار الملفات المحلية (local candidates)")
    found_any = False
    for p in LOCAL_CANDIDATES:
        st.write(f"- فحص: `{p}`")
        if p.exists():
            found_any = True
            st.success(f"تم العثور على: {p.name}")
            try:
                # نقرأ الملف ونحاول التفويض عبر gspread.service_account
                st.write("قراءة الملف ومحاولة التفويض عبر gspread.service_account(...)")
                client = gspread.service_account(filename=str(p), scopes=SCOPES)
                st.success(f"✅ نجح التفويض باستخدام الملف المحلي: {p.name}")
            except Exception:
                st.error(f"❌ فشل استخدام الملف {p.name}")
                st.code(traceback.format_exc())
        else:
            st.info("غير موجود")
    if not found_any:
        st.info("لم يتم العثور على أي ملف محلي من القائمة الافتراضية.")

# ---------- اختبار st.secrets كمصدر dict/json ----------
def test_secrets_auth():
    st.subheader("3) محاولة التفويض من st.secrets")
    tried = False
    # 1) قسم gcp_service_account
    if "gcp_service_account" in st.secrets:
        tried = True
        try_from_dict("st.secrets['gcp_service_account']", dict(st.secrets["gcp_service_account"]))
    # 2) service_account_json كنص
    if "service_account_json" in st.secrets:
        tried = True
        try:
            parsed = json.loads(st.secrets["service_account_json"])
            try_from_dict("st.secrets['service_account_json']", parsed)
        except Exception:
            st.error("service_account_json موجود لكن لا يمكن تحليله كـ JSON.")
            st.code(traceback.format_exc())
    # 3) مفاتيح منفصلة (type == service_account)
    if "type" in st.secrets and st.secrets["type"] == "service_account":
        tried = True
        try_from_dict("st.secrets (مفاتيح منفصلة)", dict(st.secrets))
    # 4) مفاتيح أساسية متفرقة
    if all(k in st.secrets for k in ["type", "project_id", "private_key", "client_email"]):
        tried = True
        try_from_dict("st.secrets (مفاتيح أساسية)", dict(st.secrets))

    if not tried:
        st.info("لم يتم العثور على بيانات اعتماد مناسبة داخل st.secrets لاختبارها.")

# ---------- اختبار متغير البيئة ----------
def test_env_auth():
    st.subheader("4) محاولة التفويض من متغير البيئة")
    env_json = os.environ.get("SERVICE_ACCOUNT_JSON") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if env_json:
        st.write("تم العثور على متغير بيئة يحتوي JSON.")
        try:
            parsed = json.loads(env_json)
            try_from_dict("ENV SERVICE_ACCOUNT_JSON", parsed)
        except Exception:
            st.error("متغير البيئة موجود لكن لا يمكن تحليله كـ JSON.")
            st.code(traceback.format_exc())
    else:
        st.info("لا يوجد متغير بيئة SERVICE_ACCOUNT_JSON أو GOOGLE_SERVICE_ACCOUNT_JSON.")

# ---------- اختبار تفويض gspread مباشر من dict (مستخدم عند الضغط) ----------
def test_authorize_from_dict_input():
    st.subheader("5) تجربة تفويض سريع من JSON مُدخل (اختياري)")
    st.write("يمكنك لصق JSON حساب الخدمة هنا (مؤقتًا) لاختبار التفويض. لا تضع المفتاح الكامل للعامة.")
    json_input = st.text_area("لصق JSON هنا (اختياري)", height=160)
    if st.button("جرب التفويض من JSON المُلصق"):
        if not json_input.strip():
            st.warning("لم تُدخل JSON للاختبار.")
        else:
            try:
                parsed = json.loads(json_input)
                try_from_dict("JSON المُلصق من المستخدم", parsed)
            except Exception:
                st.error("النص المدخل ليس JSON صالحًا.")
                st.code(traceback.format_exc())

# ---------- تنفيذ الاختبارات حسب الأزرار أو تشغيل الكل ----------
def run_sequence():
    st.info("تشغيل سلسلة الاختبارات: local -> secrets -> env")
    test_local_files()
    test_secrets_auth()
    test_env_auth()
    st.success("انتهت سلسلة الاختبارات.")

# تنفيذ حسب اختيار المستخدم
if run_all:
    run_sequence()

if run_local_btn:
    test_local_files()

if run_secrets_btn:
    inspect_secrets()
    test_secrets_auth()

if run_env_btn:
    test_env_auth()

if run_auth_btn:
    # محاولة تفويض سريع: نجرّب المصادر بالترتيب الذي حدده المستخدم في sidebar (أو الافتراضي)
    st.subheader("محاولة تفويض سريعة حسب أولوية المصادر")
    order = []
    if force_use == "استخدم ملف محلي أولاً":
        order = ["local", "secrets", "env"]
    elif force_use == "استخدم st.secrets أولاً":
        order = ["secrets", "local", "env"]
    elif force_use == "استخدم متغير البيئة أولاً":
        order = ["env", "secrets", "local"]
    else:
        order = ["local", "secrets", "env"]

    st.write("أولوية المحاولة:", order)

    success = False
    # local
    if "local" in order and not success:
        for p in LOCAL_CANDIDATES:
            if p.exists():
                st.write(f"محاولة من الملف المحلي: {p.name}")
                try:
                    client = gspread.service_account(filename=str(p), scopes=SCOPES)
                    st.success(f"نجح التفويض باستخدام الملف المحلي: {p.name}")
                    success = True
                    break
                except Exception:
                    st.error(f"فشل استخدام الملف {p.name}")
                    st.code(traceback.format_exc())
    # secrets
    if "secrets" in order and not success:
        st.write("محاولة من st.secrets...")
        try:
            creds_dict = None
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

            if creds_dict is not None:
                ok, err = try_from_dict("st.secrets (محاولة سريعة)", creds_dict)
                success = ok
            else:
                st.info("لم يتم العثور على بيانات اعتماد مناسبة داخل st.secrets.")
        except Exception:
            st.error("حدث خطأ أثناء محاولة استخدام st.secrets.")
            st.code(traceback.format_exc())

    # env
    if "env" in order and not success:
        st.write("محاولة من متغير البيئة...")
        env_json = os.environ.get("SERVICE_ACCOUNT_JSON") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if env_json:
            try:
                parsed = json.loads(env_json)
                ok, err = try_from_dict("ENV SERVICE_ACCOUNT_JSON", parsed)
                success = ok
            except Exception:
                st.error("متغير البيئة موجود لكن لا يمكن تحليله كـ JSON.")
                st.code(traceback.format_exc())
        else:
            st.info("لا يوجد متغير بيئة SERVICE_ACCOUNT_JSON أو GOOGLE_SERVICE_ACCOUNT_JSON.")

    if success:
        st.balloons()
    else:
        st.warning("لم ينجح التفويض من أي مصدر. راجع المخرجات أعلاه للتفاصيل.")

# ---------- قسم معلومات إضافية وتعليمات إصلاح سريعة ----------
st.markdown("---")
st.subheader("نصائح سريعة إذا فشل التفويض من st.secrets")
st.markdown(
    """
- **تأكد من تنسيق PRIVATE_KEY في Streamlit Secrets**: يجب أن يكون كسطر واحد مع `\\n` داخل النص، مثال:
  `PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----\\nMIIC...==\\n-----END PRIVATE KEY-----\\n"`
- **لا تقم بتحويل `\\n` إلى أسطر فعلية** عند اللصق في واجهة Secrets.
- **احذف أي دوال في الكود تعدّل قيمة `private_key`** (مثل `replace("\\n", "\\n")` أو `normalize_private_key`).
- بعد تعديل Secrets اضغط Save وانتظر دقيقة أو دقيقتين ثم أعد تحميل التطبيق.
- إذا استمر الخطأ، جرّب توليد مفتاح جديد من Google Cloud وأعد رفعه إلى Secrets.
"""
)

st.caption(f"تشغيل الفحص: {datetime.now().isoformat()}")
