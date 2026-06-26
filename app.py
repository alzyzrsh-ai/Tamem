import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# إعداد الصفحة والواجهة العربية
st.set_page_config(page_title="نظام المعالجة الرقمية والاستكشاف", layout="wide")

st.markdown("""
<style>
    .main { text-align: right; direction: rtl; }
    h1, h2, h3 { color: #007bff; }
    body { background-color: #ffffff; }
    .stButton>button { width: 100%; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🛰️ نظام استكشاف الآبار والمعالجة الرقمية للمستشعرات (Sentinel-Style)")
st.write("---")

# القائمة الجانبية للتحكم بمسار الأفكار
st.sidebar.header("⚙️ مسار العمل التسلسلي")
step = st.sidebar.radio("اختر خطوة العمل الحالية:", [
    "1️⃣ الاستكشاف والربط الحركي",
    "2️⃣ استقطاع منطقة الدراسة",
    "3️⃣ المعالجة الرقمية الفضائية (Sentinel Analysis)"
])

# نظام الذاكرة المؤقتة لحفظ البيانات بين الخطوات
if 'target_coords' not in st.session_state:
    st.session_state['target_coords'] = {'lat': 16.270000, 'lon': 43.740000}
if 'cropped_bounds' not in st.session_state:
    st.session_state['cropped_bounds'] = None

# ==================== الخطوة الأولى ====================
if step == "1️⃣ الاستكشاف والربط الحركي":
    st.subheader("📍 الخطوة الأولى: تحديد الهدف والربط مع خرائط جوجل")
    st.write("أدخل إحداثيات البئر أو الجسة المستهدفة ثم استخدم أزرار القفز السريع لفتحها ميدانياً:")
    
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("خط العرض (Latitude):", value=st.session_state['target_coords']['lat'], format="%.6f")
    with col2:
        lon = st.number_input("خط الطول (Longitude):", value=st.session_state['target_coords']['lon'], format="%.6f")
    
    # حفظ الإحداثيات المحدثة
    st.session_state['target_coords'] = {'lat': lat, 'lon': lon}
    
    # روابط القفز السريع للتطبيقات لمنع الحجب داخل المتصفح
    google_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    alpine_link = f"geo:{lat},{lon}?q={lat},{lon}(بئر_الاستكشاف)"
    
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        st.markdown(f'<a href="{google_link}" target="_blank"><button style="width:100%; background-color:#007bff; color:white; padding:12px; border:none; border-radius:8px; cursor:pointer;">🚀 افتح الموقع في خرائط جوجل</button></a>', unsafe_allow_html=True)
    with btn_col2:
        st.markdown(f'<a href="{alpine_link}"><button style="width:100%; background-color:#d9534f; color:white; padding:12px; border:none; border-radius:8px; cursor:pointer;">🗺️ افتح الموقع في AlpineQuest</button></a>', unsafe_allow_html=True)

# ==================== الخطوة الثانية ====================
elif step == "2️⃣ استقطاع منطقة الدراسة":
    st.subheader("✂️ الخطوة الثانية: استقطاع وتحديد مربع نافذة الدراسة")
    st.info(f"📍 الموقع المركزي المعتمد: {st.session_state['target_coords']['lat']}, {st.session_state['target_coords']['lon']}")
    
    st.write("حدد المسافة الجغرافية (بالدرجات) التي تود قصها واستقطاعها حول المركز لإرسال مصفوفاتها للمعالجة:")
    buffer_size = st.slider("نطاق مربع القص (Buffer Span Size):", 0.005, 0.050, 0.015, format="%.3f")
    
    c_lat = st.session_state['target_coords']['lat']
    c_lon = st.session_state['target_coords']['lon']
    
    min_lat, max_lat = c_lat - buffer_size, c_lat + buffer_size
    min_lon, max_lon = c_lon - buffer_size, c_lon + buffer_size
    
    st.write(f"📐 **أبعاد نافذة القص الحالية:**")
    st.code(f"Lat Range: [{min_lat:.4f} to {max_lat:.4f}] \nLon Range: [{min_lon:.4f} to {max_lon:.4f}]")
    
    if st.button("💾 حفظ واعتماد استقطاع هذه المنطقة"):
        st.session_state['cropped_bounds'] = (min_lat, max_lat, min_lon, max_lon)
        st.success("🎯 تم استقطاع المنطقة وتجهيز مصفوفات الصورة الجوية رقمياً! انتقل الآن للخطوة الثالثة من القائمة الجانبية.")

# ==================== الخطوة الثالثة ====================
elif step == "3️⃣ المعالجة الرقمية الفضائية (Sentinel Analysis)":
    st.subheader("🛰️ الخطوة الثالثة: برنامج المعالجة الرقمية ومحاكاة المستشعرات (Sentinel 1 & 2)")
    
    if st.session_state['cropped_bounds'] is None:
        st.warning("⚠️ يرجى الذهاب للخطوة الثانية أولاً والضغط على زر اعتماد وحفظ الاستقطاع.")
    else:
        min_lat, max_lat, min_lon, max_lon = st.session_state['cropped_bounds']
        
        st.write("⚙️ **اختر نوع المعالجة الرقمية الفضائية المراد تطبيقها على خريطة المنطقة المستقطعة:**")
        analysis_type = st.selectbox("نوع المعالجة الرقمية (Processing Type):", [
            "🟢 معالجة Sentinel-2: المؤشرات البصرية والطبوغرافية (NDVI / Geological Index)",
            "🔵 معالجة Sentinel-1: رادار النفاذية والتشققات الأرضية (SAR Lineaments & Roughness)"
        ])
        
        # توليد شبكة رقمية للمنطقة المقصوصة باستخدام Numpy
        x = np.linspace(min_lon, max_lon, 100)
        y = np.linspace(min_lat, max_lat, 100)
        X, Y = np.meshgrid(x, y)
        
        fig, ax = plt.subplots(figsize=(9, 5.5))
        
        if "Sentinel-2" in analysis_type:
            st.info("📊 تحاكي هذه المعالجة دمج النطاقات البصرية والأشعة تحت الحمراء القريبة (NIR) للكشف عن شواهد الرطوبة السطحية.")
            # مصفوفة تحاكي البصري
            Z_optical = np.sin(X*120) * np.cos(Y*120) * 30 + np.sin(X*50)*20 + 50
            contour = ax.contourf(X, Y, Z_optical, cmap='gist_earth', levels=15)
            fig.colorbar(contour, ax=ax, label="مؤشر الانعكاس الطيفي للصخور والتربة")
            ax.set_title("Sentinel-2 Simulated Optical & Moisture Processing")
            
        else:
            st.info("📡 تحاكي هذه المعالجة بيانات الرادار (SAR) ذات الاستقطاب الثنائي (VV/VH) لتوضيح الخشونة السطحية ومجاري الوديان الجافة.")
            # مصفوفة تحاكي خشونة الرادار وتفسير الصدوع
            Z_radar = (np.sin(X*200) * np.cos(Y*200))**2 * 80 + np.cos(X*30)*15
            contour = ax.contourf(X, Y, Z_radar, cmap='inferno', levels=15)
            fig.colorbar(contour, ax=ax, label="شدة الارتداد الراداري الخلفي (Backscatter Intensity dB)")
            ax.set_title("Sentinel-1 Simulated SAR Radar Lineament Processing")

        # إسقاط نقطة البئر المركزي داخل المعالجة
        ax.plot(st.session_state['target_coords']['lon'], st.session_state['target_coords']['lat'], 'ro', markersize=8, label="📍 موقع البئر المستهدف")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.legend()
        
        st.pyplot(fig)
        st.success("✅ تمت المعالجة الرقمية للمصفوفات الجغرافية المستقطعة بنجاح!")
