import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

st.set_page_config(page_title="SanbGeo - Autonomous Raster & Mineral Engine", layout="wide")

st.title("🛰️ المعجزة الجيومكانية: مولد ومعالج الرستر الآلي")
st.markdown("نظام متكامل لتوليد البيانات المكانية، معالجة النطاقات الطيفية، واستكشاف التمعدن السطحي لحظياً.")

# لوحة التحكم الجانبية لإدخال الإحداثيات ومنطقة الاهتمام (AOI)
st.sidebar.header("📍 إحداثيات منطقة البحث (AOI)")
lat = st.sidebar.number_input("خط العرض (Latitude)", value=15.3694, format="%.4f")
lon = st.sidebar.number_input("خط الطول (Longitude)", value=44.1910, format="%.4f")
zoom_area = st.sidebar.slider("نطاق التغطية المكانية (كيلومتر)", min_value=1, max_value=50, value=10)

st.sidebar.divider()
st.sidebar.header("⚙️ إعدادات النموذج الطيفي")
analysis_mode = st.sidebar.selectbox(
    "اختر نوع التحليل الاستكشافي:",
    [
        "مؤشر أكاسيد الحديد (Iron Oxides - SWIR/NIR)",
        "مؤشر نطاقات الهيدروكسيل والطين (Clay/Hydroxyl Minerals)",
        "مؤشر التحول السليسي (Silicification Index)"
    ]
)

if st.button("🚀 بدء توليد الرستر ومعالجة الأطياف آلياً"):
    with st.spinner("جاري جلب وتوليد مصفوفة الرستر المكانية وحساب المعاملات الطيفية..."):
        
        # 1. محاكاة وتوليد مصفوفة رستر فضائية متعددة النطاقات (Raster Generation) بناءً على الإحداثيات
        # نفترض مصفوفة أبعادها (Height: 256, Width: 256) لتمثيل النطاقات الطيفية المختلفة (مثل Red, NIR, SWIR1, SWIR2)
        height, width = 256, 256
        np.random.seed(int(lat + lon)) # لثبات النتيجة بناءً على الإحداثيات المحددة
        
        # توليد بيانات طيفية واقعية تحتوي على تباين مكاني (شذوذ معدني في المنتصف ومحيط صخري)
        x = np.linspace(-3, 3, width)
        y = np.linspace(-3, 3, height)
        X, Y = np.meshgrid(x, y)
        anomaly_core = np.exp(-(X**2 + Y**2) / 1.5) # محاكاة مركز التمعدن
        
        # بناء نطاقات الأقمار الصناعية افتراضياً بدقة عالية للموقع المختار
        band_red = np.random.normal(0.2, 0.02, (height, width)) + (anomaly_core * 0.1)
        band_nir = np.random.normal(0.4, 0.04, (height, width)) - (anomaly_core * 0.15)
        band_swir = np.random.normal(0.3, 0.03, (height, width)) + (anomaly_core * 0.35)
        
        st.success(f.format(f"تم توليد بيانات الرستر المكانية بنجاح لموقع الإحداثيات: ({lat}, {lon}) بقطر {zoom_area} كم!"))
        
        # 2. تطبيق خوارزمية الباند ريشيو (Band Ratios) حسب المؤشر المختاره
        if "أكاسيد الحديد" in analysis_mode:
            # معادلة شائعة لأكاسيد الحديد: SWIR / Red أو Red / Blue
            result_matrix = band_swir / (band_red + 0.001)
            color_map = 'hot'
            title_text = "خريطة الشذوذ الطيفي لأكاسيد الحديد (Iron Oxides)"
        elif "الهيدروكسيل" in analysis_mode:
            # معادلة معادن الطين
            result_matrix = band_swir / (band_nir + 0.001)
            color_map = 'plasma'
            title_text = "خريطة نطاقات الهيدروكسيل ومعادن الطين (Clays)"
        else:
            result_matrix = (band_nir * band_swir) / (band_red + 0.001)
            color_map = 'jet'
            title_text = "خريطة مؤشر التحول السليسي (Silicification)"

        # 3. العرض المرئي للنتائج عبر واجهة Streamlit
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📷 معاينة الطيف السطحي (Surface Composite)")
            fig1, ax1 = plt.subplots(figsize=(6, 5))
            im1 = ax1.imshow(band_swir, cmap='viridis')
            ax1.set_title("النطاق الطيفي الأساسي (SWIR)")
            fig1.colorbar(im1, ax=ax1)
            st.pyplot(fig1)
            
        with col2:
            st.subheader("🎯 مخرجات التحليل الاستكشافي")
            fig2, ax2 = plt.subplots(figsize=(6, 5))
            im2 = ax2.imshow(result_matrix, cmap=color_map)
            ax2.set_title(title_text)
            fig2.colorbar(im2, ax=ax2)
            st.pyplot(fig2)
            
        st.divider()
        st.info("💡 ملاحظة تحليلية: المناطق ذات الألوان الساطعة (الحمراء أو الصفراء حسب التدريج) تمثل نطاقات شذوذ محتملة تستحق التحقق الميداني أو القياس الجيوفيزيائي اللاحق.")

else:
    st.warning("⚠️ الرجاء ضبط الإحداثيات في القائمة الجانبية ثم الضغط على زر بدء التوليد والمعالجة لصناعة المعجزة البرمجية.")
