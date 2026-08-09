import base64
from datetime import datetime, timedelta, timezone
import re
from google.auth.exceptions import GoogleAuthError
from google.oauth2 import service_account
import gspread
import streamlit as st
import streamlit.components.v1 as components

# -------------------- تهيئة الصفحة وتنسيق الواجهة (CSS) --------------------
st.set_page_config(
    page_title="إدارة المنتجات", layout="centered", initial_sidebar_state="collapsed"
)

st.markdown(
    """
    <style>
    /* إخفاء القوائم الهامشية */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* محاذاة حقل الباركود وزر الكاميرا على الجوال */
    div[data-testid="stHorizontalBlock"] {
        align-items: flex-end !important;
        gap: 8px !important;
    }
    
    /* تصميم بطاقات النتائج */
    .product-card {
        background-color: #f8f9fa;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 10px;
        border-right: 5px solid #007bff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .badge-qty {
        background-color: #28a745;
        color: white;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 13px;
        font-weight: bold;
    }
    .stButton>button {
        border-radius: 10px;
        font-weight: bold;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# -------------------- الاتصال بـ Google Sheets --------------------
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
        "https://www.googleapis.com/auth/drive",
    ]
    try:
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=scopes
        )
        return gspread.authorize(creds)
    except GoogleAuthError as gae:
        raise RuntimeError("خطأ في المصادقة: " + str(gae))
    except Exception as e:
        raise RuntimeError("فشل إنشاء عميل gspread: " + str(e))


def open_products_sheet():
    gc = get_gspread_client()
    try:
        sh = gc.open("المنتجات")
    except Exception:
        sheet_key = st.secrets.get("TEST_SHEET_ID")
        if sheet_key:
            try:
                sh = gc.open_by_key(sheet_key)
            except Exception as e2:
                raise RuntimeError(
                    "فشل فتح الشيت باسم 'المنتجات' وبالمفتاح: " + str(e2)
                )
        else:
            raise RuntimeError(
                "فشل فتح الشيت باسم 'المنتجات' ولم يتم توفير TEST_SHEET_ID."
            )
    ws = sh.get_worksheet(0)
    all_values = ws.get_all_values()
    header = all_values[0] if len(all_values) >= 1 else []
    rows = all_values[1:] if len(all_values) >= 2 else []
    return gc, sh, ws, header, rows


def get_updates_sheet_in_same_spreadsheet(sh):
    try:
        ws_updates = sh.worksheet("التحديثات")
    except Exception:
        ws_updates = sh.add_worksheet(
            title="التحديثات", rows="2000", cols="10"
        )

    headers = ws_updates.row_values(1) if ws_updates.row_count > 0 else []
    expected = [
        "الباركود",
        "اسم المنتج",
        "تاريخ الصلاحية",
        "الكمية",
        "وقت التحديث",
    ]
    if headers[: len(expected)] != expected:
        if headers:
            ws_updates.delete_rows(1)
        ws_updates.insert_row(expected, index=1)
    return ws_updates


# -------------------- الدوال المساعدة والـ Callbacks --------------------
def split_barcodes(cell_text):
    if not cell_text:
        return []
    cleaned = re.sub(r"[,;|]+", " ", str(cell_text))
    return [p for p in re.split(r"\s+", cleaned.strip()) if p]


def parse_existing_date(date_str):
    if not date_str:
        return datetime.today().date()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(date_str).strip(), fmt).date()
        except ValueError:
            pass
    return datetime.today().date()


def search_products(q_barcode="", q_name=""):
    q_barcode = str(q_barcode).strip()
    q_name = str(q_name).strip().lower()

    if not q_barcode and not q_name:
        st.info("الرجاء إدخال باركود أو اسم المنتج ثم اضغط بحث.")
        return

    try:
        gc, sh, ws, header, rows = open_products_sheet()
        st.session_state["sh_id"] = sh.id

        BARCODE_IDX, NAME_IDX = 0, 1
        matches = []

        for idx, row in enumerate(rows, start=2):
            cell_barcode = row[BARCODE_IDX] if len(row) > BARCODE_IDX else ""
            cell_name = row[NAME_IDX] if len(row) > NAME_IDX else ""

            if q_barcode and cell_barcode:
                parts = split_barcodes(cell_barcode)
                if q_barcode in parts:
                    matches.append((idx, row))
                    continue

            if q_name and cell_name and q_name in cell_name.lower():
                matches.append((idx, row))

        st.session_state["search_matches"] = matches
        if not matches:
            st.warning(
                f"لم يتم العثور على نتائج مطابقة للبحث: {q_barcode or q_name}"
            )
    except Exception as e:
        st.error("فشل الاتصال بشيت المنتجات: " + str(e))


def toggle_camera_callback():
    st.session_state["show_camera"] = not st.session_state.get(
        "show_camera", False
    )


def select_product_callback(r_idx, r, qty):
    st.session_state["chosen_row"] = (r_idx, r)
    try:
        st.session_state["temp_qty"] = (
            int(float(str(qty).strip())) if str(qty).strip() else 0
        )
    except ValueError:
        st.session_state["temp_qty"] = 0


def adjust_qty_callback(delta):
    st.session_state["temp_qty"] = max(0, st.session_state["temp_qty"] + delta)


def cancel_edit_callback():
    st.session_state["chosen_row"] = None


def run_text_search_callback():
    st.session_state["chosen_row"] = None
    st.session_state["last_update"] = None
    st.session_state["search_matches"] = []
    bc = st.session_state.get("search_barcode_input", "")
    nm = st.session_state.get("search_name_input", "")
    search_products(q_barcode=bc, q_name=nm)


# -------------------- تهيئة حالة الجلسة (Session State) --------------------
if "chosen_row" not in st.session_state:
    st.session_state["chosen_row"] = None
if "sh_id" not in st.session_state:
    st.session_state["sh_id"] = None
if "last_update" not in st.session_state:
    st.session_state["last_update"] = None
if "search_matches" not in st.session_state:
    st.session_state["search_matches"] = []
if "temp_qty" not in st.session_state:
    st.session_state["temp_qty"] = 0
if "show_camera" not in st.session_state:
    st.session_state["show_camera"] = False
if "search_barcode_input" not in st.session_state:
    st.session_state["search_barcode_input"] = ""

# -------------------- التقاط الباركود الممسوح من الكاميرا --------------------
if hasattr(st, "query_params"):
    scanned_val = st.query_params.get("scanned_code")
    if scanned_val:
        del st.query_params["scanned_code"]
        st.session_state["search_barcode_input"] = scanned_val
        st.session_state["show_camera"] = False
        st.session_state["auto_scanned_barcode"] = scanned_val
else:
    qp = st.experimental_get_query_params()
    if "scanned_code" in qp:
        scanned_val = (
            qp["scanned_code"][0]
            if isinstance(qp["scanned_code"], list)
            else qp["scanned_code"]
        )
        st.experimental_set_query_params()
        st.session_state["search_barcode_input"] = scanned_val
        st.session_state["show_camera"] = False
        st.session_state["auto_scanned_barcode"] = scanned_val

# -------------------- الواجهة الرئيسية --------------------
st.title("📱 إدارة وتحديث المنتجات")

# عرض رسالة نجاح التحديث
if st.session_state.get("last_update"):
    lu = st.session_state["last_update"]
    st.success("✅ تم تحديث بيانات المنتج بنجاح!")
    st.write(f"**المنتج:** {lu.get('name','')}")
    st.write(f"**تاريخ الصلاحية الجديد:** {lu.get('expiry','')}")
    st.write(f"**الكمية الجديدة:** {lu.get('qty','')}")
    st.markdown("---")

# -------------------- قسم البحث الرئيسي --------------------
if not st.session_state.get("chosen_row"):
    st.markdown("### 🔍 البحث عن منتج")

    col_bc, col_cam = st.columns([80, 20])
    with col_bc:
        st.text_input("الباركود (مطابق 100%)", key="search_barcode_input")
    with col_cam:
        st.button(
            "📷",
            key="toggle_cam_btn",
            on_click=toggle_camera_callback,
            help="افتح كاميرا الجوال لمسح الباركود",
            use_container_width=True,
        )

    # محرك المسح المباشر المخصص والتلقائي لمتصفح Safari و آيفون
    if st.session_state.get("show_camera"):
        scanner_code = """
        <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
        
        <div id="camera-box" style="text-align: center; margin: 10px 0;">
            <button id="start-btn" onclick="startScanner()" style="
                background-color: #28a745; 
                color: white; 
                padding: 14px 20px; 
                border-radius: 10px; 
                font-weight: bold; 
                border: none;
                width: 100%;
                font-size: 16px;
                cursor: pointer;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                🎥 بدء المسح المباشر بالكاميرا
            </button>
            <div id="reader" style="width: 100%; max-width: 400px; margin: 10px auto 0 auto; border-radius: 12px; overflow: hidden;"></div>
            <div id="scan-status" style="margin-top:8px; font-size:14px; font-weight:bold; color:#333;"></div>
        </div>

        <script>
            let html5QrCode = null;

            function startScanner() {
                const btn = document.getElementById('start-btn');
                const status = document.getElementById('scan-status');
                btn.style.display = 'none';
                status.innerHTML = "⏳ جاري تشغيل الكاميرا المباشرة...";

                html5QrCode = new Html5Qrcode("reader");

                const config = { 
                    fps: 15, 
                    qrbox: { width: 260, height: 160 },
                    aspectRatio: 1.333333
                };

                html5QrCode.start(
                    { facingMode: "environment" }, 
                    config, 
                    onScanSuccess,
                    onScanFailure
                ).then(() => {
                    status.innerHTML = "🎯 وجه الكاميرا نحو الباركود لقراءته تلقائياً";
                    // التوافق المباشر مع متصفح Safari على iOS
                    const videoElem = document.querySelector("#reader video");
                    if (videoElem) {
                        videoElem.setAttribute("playsinline", "true");
                        videoElem.setAttribute("webkit-playsinline", "true");
                    }
                }).catch(err => {
                    status.innerHTML = "❌ تعذر فتح الكاميرا المباشرة: يرجى السماح بالكاميرا في Safari.";
                    btn.style.display = 'block';
                    btn.innerText = "🔄 إعادة محاولة فتح الكاميرا";
                });
            }

            function onScanSuccess(decodedText) {
                const status = document.getElementById('scan-status');
                status.innerHTML = "✅ تم القراءة تلقائياً: " + decodedText;
                if (html5QrCode) {
                    html5QrCode.stop().then(() => {
                        sendResult(decodedText);
                    }).catch(() => {
                        sendResult(decodedText);
                    });
                } else {
                    sendResult(decodedText);
                }
            }

            function onScanFailure(error) {
                // استمرار المسح عند كل إطار
            }

            function sendResult(code) {
                try {
                    const url = new URL(window.parent.location.href);
                    url.searchParams.set('scanned_code', code);
                    window.parent.location.search = url.searchParams.toString();
                } catch(e) {
                    console.error("خطأ التوجيه: ", e);
                }
            }
        </script>
        """
        components.html(scanner_code, height=380)

    # حقل اسم المنتج
    st.text_input("اسم المنتج (بحث جزئي)", key="search_name_input")

    # زر البحث
    st.button(
        "🔍 بحث عن منتج",
        on_click=run_text_search_callback,
        use_container_width=True,
        type="primary",
    )

# تنفيذ البحث الآلي عند التقاط الباركود
if st.session_state.get("auto_scanned_barcode"):
    scanned_bc = st.session_state.pop("auto_scanned_barcode")
    st.success(f"🎯 تم مسح الباركود بنجاح: **{scanned_bc}**")
    search_products(q_barcode=scanned_bc)

# -------------------- عرض بطاقات نتائج البحث --------------------
matches = st.session_state.get("search_matches", [])
if matches and not st.session_state.get("chosen_row"):
    st.subheader("نتائج البحث:")
    for idx, (r_idx, r) in enumerate(matches):
        bc = r[0] if len(r) > 0 else "بدون باركود"
        name = r[1] if len(r) > 1 else "بدون اسم"
        qty = r[3] if len(r) > 3 else "0"

        st.markdown(
            f"""
        <div class="product-card">
            <h4 style="margin:0 0 5px 0; color:#1e1e1e;">{name}</h4>
            <div style="color:#555; font-size:13px; margin-bottom:8px;">الباركود: {bc} | الصف: {r_idx}</div>
            <span class="badge-qty">الكمية الحالية: {qty}</span>
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.button(
            "✏️ تعديل وتحديث هذا المنتج",
            key=f"select_btn_{r_idx}_{idx}",
            on_click=select_product_callback,
            args=(r_idx, r, qty),
            use_container_width=True,
            type="primary",
        )
        st.write("")

# -------------------- واجهة التحديث --------------------
if st.session_state.get("chosen_row"):
    row_idx, row_values = st.session_state["chosen_row"]
    BARCODE_IDX, NAME_IDX, EXPIRY_IDX, QTY_IDX = 0, 1, 2, 3

    current_barcode_cell = (
        row_values[BARCODE_IDX] if len(row_values) > BARCODE_IDX else ""
    )
    current_name = row_values[NAME_IDX] if len(row_values) > NAME_IDX else ""
    current_expiry = (
        row_values[EXPIRY_IDX] if len(row_values) > EXPIRY_IDX else ""
    )

    st.markdown("---")
    st.markdown(f"### 📝 تحديث: **{current_name or '(بدون اسم)'}**")
    st.caption(f"الباركود: {current_barcode_cell} | الصف بالمستند: {row_idx}")

    # أزرار تحكم سريعة بالكمية
    st.write("**تعديل الكمية:**")
    col_m10, col_m1, col_val, col_p1, col_p10 = st.columns(5)

    with col_m10:
        st.button(
            "-10",
            on_click=adjust_qty_callback,
            args=(-10,),
            use_container_width=True,
        )
    with col_m1:
        st.button(
            "-1",
            on_click=adjust_qty_callback,
            args=(-1,),
            use_container_width=True,
        )
    with col_val:
        st.markdown(
            f"<h3 style='text-align: center; margin:0;'>{st.session_state['temp_qty']}</h3>",
            unsafe_allow_html=True,
        )
    with col_p1:
        st.button(
            "+1",
            on_click=adjust_qty_callback,
            args=(1,),
            use_container_width=True,
        )
    with col_p10:
        st.button(
            "+10",
            on_click=adjust_qty_callback,
            args=(10,),
            use_container_width=True,
        )

    # حقل إدخال يدوي للكمية
    new_qty = st.number_input(
        "أو ادخل الكمية يدوياً",
        min_value=0,
        step=1,
        value=st.session_state["temp_qty"],
        key="manual_qty_input",
    )
    st.session_state["temp_qty"] = new_qty

    # حقل تاريخ الصلاحية
    default_date = parse_existing_date(current_expiry)
    new_expiry = st.date_input("تاريخ الصلاحية الجديد", value=default_date)

    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button(
            "💾 حفظ التحديث الآن", type="primary", use_container_width=True
        ):
            try:
                gc = get_gspread_client()
                sh = gc.open_by_key(st.session_state["sh_id"])
                ws = sh.get_worksheet(0)

                expiry_str = new_expiry.strftime("%Y-%m-%d")
                new_qty_str = str(new_qty)

                ws.update(f"C{row_idx}:D{row_idx}", [[expiry_str, new_qty_str]])

                ws_updates = get_updates_sheet_in_same_spreadsheet(sh)
                sa_time = datetime.now(timezone(timedelta(hours=3)))
                update_time = sa_time.strftime("%Y-%m-%d %H:%M:%S")

                new_update_row = [
                    current_barcode_cell,
                    current_name,
                    expiry_str,
                    new_qty_str,
                    update_time,
                ]
                ws_updates.append_row(
                    new_update_row, value_input_option="USER_ENTERED"
                )

                st.session_state["last_update"] = {
                    "name": current_name,
                    "expiry": expiry_str,
                    "qty": new_qty_str,
                }
                st.session_state["chosen_row"] = None
                st.session_state["search_matches"] = []

                st.rerun()
            except Exception as e:
                st.error("حدث خطأ أثناء حفظ التحديثات: " + str(e))

    with col_cancel:
        st.button(
            "❌ إلغاء", on_click=cancel_edit_callback, use_container_width=True
        )
