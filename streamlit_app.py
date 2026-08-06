import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import datetime

st.set_page_config(page_title="نظام تحديث المنتجات بالباركود", layout="centered")
st.title("📱 ماسح الباركود وتحديث المستودع")

# 1. الاتصال بالجوجل شيت (باستخدام شفرة الحماية المجانية)
try:
    creds_dict = st.secrets["gcp_service_account"]
    # Correct scopes for Google Sheets / Drive API
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # جلب الملف باستخدام معرف الشيت المخزن في الأسرار
    sheet = client.open_by_key(st.secrets["sheet_id"]) 
    products_sheet = sheet.worksheet("المنتجات")
    updates_sheet = sheet.worksheet("التحديثات")
except Exception as e:
    st.error("انتظر! هناك مشكلة في الاتصال بالجوجل شيت، تأكد من الإعدادات في الأسفل.")
    st.exception(e)
    st.stop()

# 2. تشغيل الكاميرا للمتصفح أو الجوال
img_file_buffer = st.camera_input("وجه الكاميرا نحو باركود المنتج")

if img_file_buffer is not None:
    bytes_data = img_file_buffer.getvalue()
    # Decode image bytes to OpenCV image
    cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
    
    if cv2_img is None:
        st.error("لم أتمكن من قراءة الصورة، حاول مرة أخرى.")
    else:
        # convert to grayscale — pyzbar often works better on gray images
        try:
            gray = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)
        except Exception:
            # if conversion fails, fall back to original
            gray = cv2_img

        barcodes = decode(gray)
        
        if barcodes:
            # take the first barcode found (or iterate over barcodes if you want all)
            try:
                barcode_data = barcodes[0].data.decode('utf-8')
            except Exception as e:
                st.error("حدث خطأ أثناء استخراج بيانات الباركود.")
                st.exception(e)
            else:
                st.success(f"✅ تم قراءة الباركود بنجاح: {barcode_data}")
                
                # 3. البحث عن اسم المنتج في الصفحة الأولى (المنتجات)
                try:
                    cell = products_sheet.find(barcode_data)
                    row_data = products_sheet.row_values(cell.row)
                    product_name = row_data[1] if len(row_data) > 1 else ""
                    
                    st.info(f"📦 المنتج المكتشف: {product_name}")
                    
                    # 4. نموذج يدخل فيه المستخدم البيانات الفارغة
                    with st.form("update_form"):
                        expiry_date = st.date_input("تاريخ الصلاحية الجديد:", value=datetime.date.today())
                        quantity = st.number_input("الكمية الحالية المدخلة:", min_value=1, value=1, step=1)
                        
                        submitted = st.form_submit_button("إرسال التحديث للصفحة الثا��ية")
                        
                        if submitted:
                            # إضافة سطر جديد في صفحة (التحديثات)
                            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            try:
                                updates_sheet.append_row([
                                    barcode_data, 
                                    product_name, 
                                    str(expiry_date), 
                                    int(quantity), 
                                    current_time
                                ])
                                st.balloons()
                                st.success("🎉 تم تسجيل البيانات بنجاح في صفحة التحديثات!")
                            except Exception as e:
                                st.error("حدث خطأ أثناء حفظ التحديث في جوجل شيت.")
                                st.exception(e)
                except gspread.exceptions.CellNotFound:
                    st.error("❌ هذا الباركود غير مسجل في قاعدة بيانات المنتجات الأولى.")
                except Exception as e:
                    st.error("حدث خطأ أثناء البحث في صفحة المنتجات.")
                    st.exception(e)
        else:
            st.warning("⚠️ الباركود غير واضح، يرجى تقريب الكاميرا أو تحسين الإضاءة.")
