# streamlit_app.py
import streamlit as st
import traceback
import base64
from google.oauth2 import service_account
import gspread

st.set_page_config(page_title="Google Sheets Auth Debug", layout="centered")

st.title("تشخيص اتصال Google Sheets")

# --- قراءة الـ secrets مع دعم بديل Base64 ---
def get_private_key():
    # حاول قراءة المفتاح كـ multiline PRIVATE_KEY أولاً
    pk = st.secrets.get("PRIVATE_KEY")
    if pk:
        return pk
    # لو ما موجود، حاول قراءة Base64 وفكّه
    pk_b64 = st.secrets.get("PRIVATE_KEY_B64")
    if pk_b64:
        try:
            decoded = base64.b64decode(pk_b64).decode("utf-8")
            return decoded
        except Exception as e:
            st.error("فشل فك Base64 للمفتاح: " + str(e))
            return None
    return None

# --- تشخيص سريع لوجود المتغيرات ---
st.header("فحص المتغيرات في Secrets")
required_keys = [
    "TYPE", "PROJECT_ID", "PRIVATE_KEY_ID", "CLIENT_EMAIL",
    "CLIENT_ID", "AUTH_URI", "TOKEN_URI", "AUTH_PROVIDER_CERT_URL",
    "CLIENT_CERT_URL"
]
present = {k: (k in st.secrets) for k in required_keys}
for k, ok in present.items():
    st.write(f"**{k}**:", "✅ موجود" if ok else "❌ مفقود")

pk = get_private_key()
st.write("**PRIVATE_KEY موجود:**", "✅" if pk else "❌")
if pk:
    st.write("**يبدأ بـ BEGIN:**", pk.strip().startswith("-----BEGIN PRIVATE KEY-----"))
    st.write("**ينتهي بـ END:**", pk.strip().endswith("-----END PRIVATE KEY-----"))
    st.write("**عدد أسطر المفتاح:**", len(pk.splitlines()))
    # عرض أول وآخر سطر للتأكد (بدون كشف كامل المفتاح)
    lines = pk.splitlines()
    if len(lines) >= 2:
        st.write("أول سطر:", lines[0])
        st.write("آخر سطر:", lines[-1])

# --- محاولة إنشاء Credentials والاتصال بـ Google Sheets ---
st.header("محاولة الاتصال بـ Google Sheets (تشخيصي)")
if st.button("جرّب الاتصال الآن"):
    try:
        # جهّز info من secrets
        info = {
            "type": st.secrets.get("TYPE"),
            "project_id": st.secrets.get("PROJECT_ID"),
            "private_key_id": st.secrets.get("PRIVATE_KEY_ID"),
            "private_key": pk,
            "client_email": st.secrets.get("CLIENT_EMAIL"),
            "client_id": st.secrets.get("CLIENT_ID"),
            "auth_uri": st.secrets.get("AUTH_URI"),
            "token_uri": st.secrets.get("TOKEN_URI"),
            "auth_provider_x509_cert_url": st.secrets.get("AUTH_PROVIDER_CERT_URL"),
            "client_x509_cert_url": st.secrets.get("CLIENT_CERT_URL")
        }

        missing = [k for k, v in info.items() if not v]
        if missing:
            st.error("في متغيرات مفقودة في Secrets: " + ", ".join(missing))
        else:
            st.info("جاري إنشاء Credentials...")
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            st.success("تم إنشاء Credentials بنجاح. محاولة التفويض والاتصال...")
            gc = gspread.authorize(creds)
            # تجربة فتح ملف تجريبي (غير ملزم، فقط اختبار)
            # استبدل 'SHEET_ID_OR_NAME' باسم أو ID شيت مشترك مع client_email
            try:
                sh = gc.open_by_key(st.secrets.get("TEST_SHEET_ID")) if st.secrets.get("TEST_SHEET_ID") else None
                if sh:
                    st.success("تم الوصول إلى Google Sheet بنجاح: " + sh.title)
                else:
                    st.info("لم يتم تحديد TEST_SHEET_ID في Secrets. الاتصال ناجح لكن لم يتم فتح شيت للاختبار.")
            except Exception as e:
                st.error("فشل فتح Google Sheet: " + str(e))
    except Exception as e:
        st.error("حدث استثناء أثناء إنشاء Credentials أو التفويض.")
        st.text(traceback.format_exc())

# --- تعليمات سريعة للمستخدم ---
st.header("تعليمات سريعة لحل المشاكل الشائعة")
st.markdown("""
- **أفضل طريقة**: ضع `PRIVATE_KEY` داخل ثلاث علامات اقتباس ثلاثية `\"\"\"` في Streamlit Secrets (multiline).
- **بديل آمن**: ضع المفتاح مشفّرًا بـ Base64 في `PRIVATE_KEY_B64` ثم فكّه داخل التطبيق (كما في الكود أعلاه).
- **تأكد** أن `client_email` مشارك مع Google Sheet كـ Editor.
- **لو ظهر `invalid_grant`**: جرّب إنشاء Key جديد من Google Cloud (IAM → Service Accounts → Keys → Create JSON) ثم حدّث Secrets.
- **تأكد من الترميز**: احفظ أي ملفات نصية بـ UTF-8 بدون BOM.
- بعد أي تعديل في Secrets: اضغط Save ثم **Restart app** في Streamlit Cloud.
""")

st.caption("أرسل لي نتائج الفحص (قيمة PRIVATE_KEY موجودة؟ وعدد الأسطر) أو انسخ السطر الأحمر الكامل من الـ Logs لو استمر الخطأ.")
