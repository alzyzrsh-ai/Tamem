import streamlit as st
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt

# واجهة تطبيق المهندس عبدالعزيز البرعي
st.set_page_config(page_title="Geophysics Analysis", layout="wide")
st.title("🌍 نظام التحليل الهيدروجيولوجي الذكي")
st.sidebar.header("🛠️ لوحة التحكم")

# أيقونة رفع الصور الميدانية
uploaded_file = st.sidebar.file_uploader("ارفع الصورة الجوية للموقع", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    img = Image.open(uploaded_file).convert('RGB')
    data = np.array(img)
    # حساب التباين والامتصاص (مؤشر كثافة المياه)
    absorption = 255 - np.mean(data, axis=2)

    col1, col2 = st.columns(2)
    
    with col1:
        if st.button('🔍 تشغيل التحليل الطيفي'):
            st.subheader("نتائج امتصاص الأطياف")
            fig1, ax1 = plt.subplots()
            ax1.imshow(absorption, cmap='YlGnBu')
            plt.axis('off')
            st.pyplot(fig1)

    with col2:
        if st.button('📈 توليد خطوط الكنتور'):
            st.subheader("خريطة التباين الكنتورية")
            fig2, ax2 = plt.subplots()
            ax2.imshow(img, alpha=0.6)
            contours = ax2.contour(absorption, levels=12, cmap='jet')
            ax2.clabel(contours, inline=True, fontsize=8)
            plt.axis('off')
            st.pyplot(fig2)
else:
    st.info("بانتظار رفع صورة الموقع الجوية لبدء التحليل الهندسي...")
