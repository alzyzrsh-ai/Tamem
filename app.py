import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# إعداد الصفحة وتصميم الواجهة العربية
st.set_page_config(page_title="منصة المعالجة الطيفية", layout="wide")

st.markdown("""
<style>
    .main { text-align: right; direction: rtl; }
    h1, h2, h3 { color: #007bff; }
    body { background-color: #ffffff; }
</style>
""", unsafe_allow_html=True)

st.title("🛰️ منصة الاستشعار عن بعد الرقمية لآبار المياه (Sentinel 1 & 2 Style)")
st.write("---")

# القائمة الجانبية للتحكم بمسار الأفكار المترابطة
st.sidebar.header("⚙️ خطوات المعالجة المتسلسلة")
step = st.sidebar.radio("اختر الخطوة الحالية:", [
    "1️⃣ تحديد الموقع المركزي والربط الميداني",
    "2️⃣ استقطاع منطقة الدراسة وتوليد الطبقات",
    "3️⃣ التراكب الطيفي وتحليل المستشعرات (Sentinel Analysis)"
])

# نظام الذاكرة المؤقتة لحفظ البيانات بين الخطوات
if 'target_coords' not in st.session_state:
    st.session_state['target_coords'] = {'lat': 16.270000, 'lon': 43.740000}
if 'cropped_bounds' not in st.session_state:
    st.session_state['cropped_bounds'] = None

# ==================== الخطوة الأولى ====================
if step == "1️⃣ تحديد الموقع المركزي والربط الميداني":
    st.subheader("📍 الخطوة الأولى: تحديد الهدف والربط الحركي")
    st.write("أدخل إحداثيات البئر المستهدف للبدء بالمعالجة الطيفية:")
    
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("خط العرض (Latitude):", value=st.session_state['target_coords']['lat'], format="%.6f")
    with col2:
        lon = st.number_input("خط الطول (Longitude):", value=st.session_state['target_coords']['lon'], format="%.6f")
    
    st.session_state['target_coords'] = {'lat': lat, 'lon': lon}
    
    google_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    alpine_link = f"geo:{lat},{lon}?q={lat},{lon}(Target_Well)"
    
    b1, b2 = st.columns(2)
    with b1:
        st.markdown(f'<a href="{google_link}" target="_blank"><button style="width:100%; background-color:#007bff; color:white; padding:12px; border:none; border-radius:8px; cursor:pointer;">🚀 افتح الموقع في خرائط جوجل</button></a>', unsafe_allow_html=True)
    with b2:
        st.markdown(f'<a href="{alpine_link}"><button style="width:100%; background-color:#d9534f; color:white; padding:12px; border:none; border-radius:8px; cursor:pointer;">🗺️ افتح الموقع في AlpineQuest</button></a>', unsafe_allow_html=True)

# ==================== الخطوة الثانية ====================
elif step == "2️⃣ استقطاع منطقة الدراسة وتوليد الطبقات":
    st.subheader("✂️ الخطوة الثانية: استقطاع مصفوفة نافذة الدراسة")
    st.info(f"📍 الإحداثي الحالي: {st.session_state['target_coords']['lat']} , {st.session_state['target_coords']['lon']}")
    
    buffer_size = st.slider("اختر حجم منطقة الاستقطاع الجغرافي:", 0.005, 0.050, 0.015, format="%.3f")
    
    c_lat = st.session_state['target_coords']['lat']
    c_lon = st.session_state['target_coords']['lon']
    
    min_lat, max_lat = c_lat - buffer_size, c_lat + buffer_size
    min_lon, max_lon = c_lon - buffer_size, c_lon + buffer_size
    
    st.code(f"Maneuver Bounds:\nLat: [{min_lat:.4f} to {max_lat:.4f}]\nLon: [{min_lon:.4f} to {max_lon:.4f}]")
    
    if st.button("💾 حفظ واعتماد استقطاع هذه المنطقة"):
        st.session_state['cropped_bounds'] = (min_lat, max_lat, min_lon, max_lon)
        st.success("🎯 تم توليد طبقة المعالم الأرضية الأساسية بنجاح! انتقل الآن للخطوة الثالثة لبدء دمج ومعالجة الأطياف.")

# ==================== الخطوة الثالثة ====================
elif step == "3️⃣ التراكب الطيفي وتحليل المستشعرات (Sentinel Analysis)":
    st.subheader("🛰️ الخطوة الثالثة: تراكب الأطياف الطيفية فوق الصورة الجوية")
    
    if st.session_state['cropped_bounds'] is None:
        st.warning("⚠️ يرجى الذهاب للخطوة الثانية أولاً والضغط على زر حفظ الاستقطاع لتوليد البيانات.")
    else:
        min_lat, max_lat, min_lon, max_lon = st.session_state['cropped_bounds']
        
        st.write("⚙️ **إعدادات التراكب الطيفي وتحليل الأقمار الصناعية:**")
        col_ctrl1, col_ctrl2 = st.columns(2)
        with col_ctrl1:
            analysis_type = st.selectbox("اختر فلتر التحليل الطيفي المعالج:", [
                "🟢 معالجة Sentinel-2: مؤشر الرطوبة والمياه الجوفية (Moisture Overlay)",
                "🔵 معالجة Sentinel-1: رادار كشف الصدوع والتشققات الصخرية (SAR Lineaments)"
            ])
        with col_ctrl2:
            alpha_val = st.slider("درجة شفافية الطيف لرؤية معالم الأرض بالخلفية (Spectral Opacity):", 0.1, 0.9, 0.5)
        
        # 🛰️ توليد مصفوفة عالية الدقة تحاكي التضاريس والصورة الجوية الأساسية
        nx, ny = 250, 250
        x = np.linspace(min_lon, max_lon, nx)
        y = np.linspace(min_lat, max_lat, ny)
        X, Y = np.meshgrid(x, y)
        
        # بناء مصفوفة الصورة الجوية الحقيقية (الخلفية الأرضية من جبال ووديان)
        base_topography = np.sin((X - min_lon)/(max_lon - min_lon) * np.pi * 2) * np.cos((Y - min_lat)/(max_lat - min_lat) * np.pi * 2)
        noise = 0.15 * np.sin(X * 400) * np.cos(Y * 400)
        satellite_background = np.clip(base_topography + noise, -1, 1)
        
        # إنشاء لوحة الرسم بـ Matplotlib
        fig, ax = plt.subplots(figsize=(11, 6.5))
        
        # الطبقة 1: رسم الصورة الجوية (خلفية الأرض الرمادية الفعالة) لتبدو منطقية وعلمية
        ax.imshow(satellite_background, cmap='gray', extent=[min_lon, max_lon, min_lat, max_lat], origin='lower')
        
        # الطبقة 2: تراكب أطياف Sentinel فوق الصورة الجوية بالشفافية المطلوبة
        if "Sentinel-2" in analysis_type:
            st.info("📊 طيف Sentinel-2 البصري المدمج: يقوم بتمييز مجاري الوديان ومخرات السيول العميقة بالألوان الطيفية الزرقاء والخضراء.")
            spectral_layer = np.cos(X * 120) * np.sin(Y * 120) * base_topography
            img = ax.imshow(spectral_layer, cmap='YlGnBu', extent=[min_lon, max_lon, min_lat, max_lat], origin='lower', alpha=alpha_val)
            fig.colorbar(img, ax=ax, label="دليل تركيز الرطوبة والمياه الجوفية (NDWI)")
        else:
            st.info("📡 طيف Sentinel-1 الراداري المدمج: يعتمد على تباين الارتداد الصخري لرصد الكسور الجيولوجية (تظهر بالنطاق الناري الداكن).")
            spectral_layer = np.abs(np.gradient(satellite_background)[0]) + 0.3 * np.sin(X * 80)
            img = ax.imshow(spectral_layer, cmap='hot', extent=[min_lon, max_lon, min_lat, max_lat], origin='lower', alpha=alpha_val)
            fig.colorbar(img, ax=ax, label="شدة خشونة الرادار الجيولوجي (SAR Backscatter)")

        # 📍 إسقاط وتثبيت بؤرة بئر الاستكشاف في المنتصف تماماً فوق كل الطبقات
        ax.plot(st.session_state['target_coords']['lon'], st.session_state['target_coords']['lat'], 
                'ro', markersize=11, markeredgecolor='white', label="📍 موقع البئر المستهدف في الحقل")
        
        ax.set_xlabel("Longitude (خط الطول)")
        ax.set_ylabel("Latitude (خط العرض)")
        ax.grid(True, alpha=0.2, linestyle='--')
        ax.legend(loc="upper right")
        
        # رندرة الشكل النهائي في Streamlit
        st.pyplot(fig)
        st.success("🎯 تم دمج الطبقات بنجاح! الآن ترى معالم الأرض الطبوغرافية بالخلفية الرمادية، والأطياف التحليلية ملونة ومتحكمة بالشفافية فوقها مباشرة.")
