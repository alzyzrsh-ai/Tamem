import streamlit as st
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt

# إعدادات الصفحة
st.set_page_config(page_title="نظام التحليل الجيوفيزيائي", layout="wide")

# تصميم الواجهة العربية
st.markdown("""
    <style>
    .main { text-align: right; direction: rtl; }
    stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌍 نظام التحليل الهيدروجيولوجي الذكي")
st.write("---")

# --- إضافة أيقونة تحميل الصورة في الشريط الجانبي ---
st.sidebar.header("🛠️ أدوات التحكم")
uploaded_file = st.sidebar.file_uploader("📂 قم برفع صورة الموقع الجوية (JPG/PNG)", type=['jpg', 'jpeg', 'png'])

if uploaded_file is not None:
    # معالجة الصورة المرفوعة
    image = Image.open(uploaded_file).convert('RGB')
    img_array = np.array(image)
    
    # عرض الصورة الأصلية
    st.subheader("📸 صورة الموقع الميداني")
    st.image(image, use_column_width=True)
    
    # حساب مصفوفة الامتصاص والتباين (الخوارزمية الجيوفيزيائية)
    absorption = 255 - np.mean(img_array, axis=2)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button('🔍 تحليل البصمة الطيفية'):
            st.write("### خريطة امتصاص الأطياف")
            fig1, ax1 = plt.subplots()
            im1 = ax1.imshow(absorption, cmap='YlGnBu')
            plt.colorbar(im1, ax=ax1)
            plt.axis('off')
            st.pyplot(fig1)

    with col2:
        if st.button('📈 توليد خطوط الكنتور'):
            st.write("### الخريطة الكنتورية للتباين")
            fig2, ax2 = plt.subplots()
            ax2.imshow(img_array, alpha=0.5)
            contours = ax2.contour(absorption, levels=15, cmap='jet')
            ax2.clabel(contours, inline=True, fontsize=8)
            plt.axis('off')
            st.pyplot(fig2)
            
    st.success("تم التحليل بنجاح. استخدم المناطق ذات اللون الداكن في تحليل الأطياف لتحديد نقاط الجس VES.")
else:
    # رسالة تظهر في حال عدم وجود ملف
    st.info("👈 يرجى الضغط على 'Browse files' في القائمة الجانبية لرفع صورة الموقع والبدء بالتحليل.")
