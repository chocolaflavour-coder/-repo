import streamlit as st
from datetime import datetime, parse

# -------------------- 1. CSS لتصميم يشبه تطبيق الجوال --------------------
st.set_page_config(page_title="تطبيق المنتجات", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    /* إخفاء الهيدر والفوتير الخاص بـ Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* تحسين شكل البطاقات للأجهزة الذكية */
    .product-card {
        background-color: #f8f9fa;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 10px;
        border-right: 5px solid #007bff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .badge-success { background-color: #28a745; color: white; padding: 3px 8px; border-radius: 6px; font-size: 12px; }
    .badge-warning { background-color: #ffc107; color: black; padding: 3px 8px; border-radius: 6px; font-size: 12px; }
    
    /* تكبير أزرار اللمس والجوال */
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 48px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# -------------------- 2. خيار مسح الباركود بالكاميرا --------------------
st.title("📱 إدارة المخزون")

tab1, tab2 = st.tabs(["🔍 بحث نصي", "📷 مسح بالكاميرا"])

with tab2:
    camera_image = st.camera_input("وجّه كاميرا الجوال للباركود")
    if camera_image:
        st.info("جاري تحليل الباركود من الصورة...")
        # يمكن دمج مكتبة pyzbar أو zxing هنا لتحليل الباركود مباشرة من الكاميرا

# -------------------- 3. عرض النتائج كـ بطاقات (Product Cards) --------------------
# (تُنفذ داخل الجزء الخاص بعرض النتائج)
matches = st.session_state.get("search_matches", [])

if matches and not st.session_state.get("chosen_row"):
    st.subheader("اختر المنتج:")
    for idx, (r_idx, r) in enumerate(matches):
        bc = r[0] if len(r) > 0 else "بدون باركود"
        name = r[1] if len(r) > 1 else "بدون اسم"
        qty = r[3] if len(r) > 3 else "0"
        
        # تصميم البطاقة
        with st.container():
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                st.markdown(f"""
                <div class="product-card">
                    <h4 style="margin:0;">{name}</h4>
                    <small>الباركود: {bc}</small><br>
                    <span class="badge-success">الكمية الحالية: {qty}</span>
                </div>
                """, unsafe_allow_html=True)
            with col_btn:
                # زر اختيار كبير ومناسب لشبكية اللمس
                if st.button("تحديث ✏️", key=f"select_btn_{r_idx}"):
                    st.session_state["chosen_row"] = (r_idx, r)
                    st.rerun()

# -------------------- 4. أزرار تعديل الكمية السريعة (+ / -) --------------------
if st.session_state.get("chosen_row"):
    row_idx, row_values = st.session_state["chosen_row"]
    current_qty = int(row_values[3]) if len(row_values) > 3 and str(row_values[3]).isdigit() else 0

    st.markdown("---")
    st.markdown(f"### تعديل كمية: **{row_values[1]}**")
    
    # تحكم سريع بالكمية بضغطة زر
    if "temp_qty" not in st.session_state:
        st.session_state["temp_qty"] = current_qty

    col_m10, col_m1, col_val, col_p1, col_p10 = st.columns(5)
    
    with col_m10:
        if st.button("-10"): st.session_state["temp_qty"] = max(0, st.session_state["temp_qty"] - 10)
    with col_m1:
        if st.button("-1"): st.session_state["temp_qty"] = max(0, st.session_state["temp_qty"] - 1)
    with col_val:
        st.markdown(f"<h3 style='text-align: center;'>{st.session_state['temp_qty']}</h3>", unsafe_allow_html=True)
    with col_p1:
        if st.button("+1"): st.session_state["temp_qty"] += 1
    with col_p10:
        if st.button("+10"): st.session_state["temp_qty"] += 10

    # حفظ القيمة في المدخل الرئيسي
    new_qty = st.session_state["temp_qty"]
