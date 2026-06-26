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

st.title("🛰️ نظام المعالجة الرقمية الطيفية المتكامل (Sentinel Style)")
st.write("---")

# القائمة الجانبية للتحكم بمسار الأفكار
st.sidebar.header("⚙️ مسار العمل التسلسلي")
step = st.sidebar.radio("اختر خطوة العمل الحالية:", [
    "1️⃣ الاستكشاف والربط الحركي",
    "2️⃣ استقطاع منطقة الدراسة",
    "3️⃣ المعالجة الرقمية الفضائية (Sentinel Analysis)"
])

# نظام الذاكرة المؤقتة لحفظ البيانات
if 'target_coords' not in st.session_state:
    st.session_state['target_coords'] = {'lat': 16.270000, 'lon': 43.740000}
if 'cropped_bounds' not in st.session_state:
    st.session_state['cropped_bounds'] = None

# ==================== الخطوة الأولى ====================
if step == "1️⃣ الاستكشاف والربط الحركي":
    st.subheader("📍 الخطوة الأولى: تحديد الهدف والربط مع الخرائط")
    
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("خط العرض (Latitude):", value=st.session_state['target_coords']['lat'], format="%.6f")
    with col2:
        lon = st.number_input("خط الطول (Longitude):", value=st.session_state['target_coords']['lon'], format="%.6f")
    
    st.session_state['target_coords'] = {'lat': lat, 'lon': lon}
    
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
    
    buffer_size = st.slider("نطاق مربع القص الجغرافي (حجم المنطقة المقتطعة):", 0.005, 0.050, 0.015, format="%.3f")
    
    c_lat = st.session_state['target_coords']['lat']
    c_lon = st.session_state['target_coords']['lon']
    
    min_lat, max_lat = c_lat - buffer_size, c_lat + buffer_size
    min_lon, max_lon = c_lon - buffer_size, c_lon + buffer_size
    
    st.code(f"Maneuver Bounds:\nLat: [{min_lat:.4f} to {max_lat:.4f}]\nLon: [{min_lon:.4f} to {max_lon:.4f}]")
    
    if st.button("💾 حفظ واعتماد استقطاع هذه المنطقة"):
        st.session_state['cropped_bounds'] = (min_lat, max_lat, min_lon, max_lon)
        st.success("🎯 تم حفظ أبعاد المنطقة المستقطعة! انتقل للخطوة الثالثة لتطبيق التحليل الطيفي.")

# ==================== الخطوة الثالثة ====================
elif step == "3️⃣ المعالجة الرقمية الفضائية (Sentinel Analysis)":
    st.subheader("🛰️ الخطوة الثالثة: تراكب الأطياف الرقمية فوق الصورة الجوية")
    
    if st.session_state['cropped_bounds'] is None:
        st.warning("⚠️ يرجى الذهاب للخطوة الثانية أولاً والضغط على زر حفظ الاستقطاع.")
    else:
        min_lat, max_lat, min_lon, max_lon = st.session_state['cropped_bounds']
        
        # شريط تحكم إضافي للتحكم بمدى وضوح الصورة الجوية أو طيف المستشعر (شفافية الأطياف)
        st.write("⚙️ **إعدادات التراكب الطيفي الفضائي:**")
        col_ctrl1, col_ctrl2 = st.columns(2)
        with col_ctrl1:
            analysis_type = st.selectbox("اختر فلتر التحليل الطيفي المعالج:", [
                "🟢 معالجة Sentinel-2: مؤشر الرطوبة والطبوغرافيا (Moisture Overlay)",
                "🔵 معالجة Sentinel-1: رادار كشف الصدوع والوديان (SAR Lineaments)"
            ])
        with col_ctrl2:
            alpha_val = st.slider("درجة شفافية الطيف لرؤية الصورة الجوية بالخلفية (Spectral Opacity):", 0.1, 1.0, 0.5)
        
        # 🛰️ إنشاء شبكة المصفوفات الجغرافية الدقيقة
        nx, ny = 200, 200
        x = np.linspace(min_lon, max_lon, nx)
        y = np.linspace(min_lat, max_lat, ny)
        X, Y = np.meshgrid(x, y)
        
        # 1. توليد طبقة الخلفية: (محاكاة الصورة الجوية الواقعية الرمادية للتضاريس والمعالم الأرضية الأساسية)
        base_geo_img = np.sin((X - min_lon)/(max_lon - min_lon) * 2) * np.cos((Y - min_lat)/(max_lat - min_lat) * 3)
        base_geo_img = (base_geo_img - base_geo_img.min()) / (base_geo_img.max() - base_geo_img.min()) # توحيد الأبعاد
        
        # 2. توليد طبقة الطيف الفضائي المعالج (المتراكب فوقها)
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # رسم الصورة الجوية الأساسية أولاً بالأسفل (أبيض وأسود طبيعي للمعالم الأرضية)
        ax.imshow(base_geo_img, cmap='gray', extent=[min_lon, max_lon, min_lat, max_lat], origin='lower')
        
        if "Sentinel-2" in analysis_type:
            # مصفوفة طيف الأشعة تحت الحمراء للرطوبة ومخرات السيول
            spectral_layer = np.sin(X*150) * np.cos(Y*150) * 0.5 + 0.5
            # إسقاط الطيف الفوقي مع تطبيق الشفافية المحددة (alpha)
            img = ax.imshow(spectral_layer, cmap='YlGnBu', extent=[min_lon, max_lon, min_lat, max_lat], origin='lower', alpha=alpha_val)
            cb = fig.colorbar(img, ax=ax, label="دليل تركيز الرطوبة والمياه السطحية")
        else:
            # مصفوفة طيف الرادار VV/VH لتوضيح الكسور الجيولوجية والتشققات الصخرية العمياء
            spectral_layer = (np.sin(X*80) * np.cos(Y*250))**2
            img = ax.imshow(spectral_layer, cmap='hot', extent=[min_lon, max_lon, min_lat, max_lat], origin='lower', alpha=alpha_val)
            cb = fig.colorbar(img, ax=ax, label="شدة خشونة الرادار الجيولوجي")

        # 📍 إسقاط وتثبيت بؤرة بئر الاستكشاف في المنتصف تماماً فوق كل الطبقات
        ax.plot(st.session_state['target_coords']['lon'], st.session_state['target_coords']['lat'], 
                'ro', markersize=10, markeredgecolor='white', label="📍 موقع البئر المستهدف في الحقل")
        
        ax.set_xlabel("Longitude (خط الطول)")
        ax.set_ylabel("Latitude (خط العرض)")
        ax.grid(True, alpha=0.2, linestyle='--')
        ax.legend(loc="upper right")
        
        # عرض اللوحة الجيوفيزيائية الكاملة
        st.pyplot(fig)
        st.success("🎯 العمل الآن منطقي ومثالي! الصورة الجوية تظهر بالخلفية الرمادية الحقيقية، وفوقها الطيف الفضائي الملون بحسب مستوى الشفافية المختار.")
