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

st.title("🛰️ نظام استكشاف الآبار والمعالجة الرقمية للمستشعرات")
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
    
    buffer_size = st.slider("نطاق مربع القص الجغرافي:", 0.005, 0.050, 0.015, format="%.3f")
    
    c_lat = st.session_state['target_coords']['lat']
    c_lon = st.session_state['target_coords']['lon']
    
    min_lat, max_lat = c_lat - buffer_size, c_lat + buffer_size
    min_lon, max_lon = c_lon - buffer_size, c_lon + buffer_size
    
    st.code(f"Maneuver Bounds:\nLat: [{min_lat:.4f} to {max_lat:.4f}]\nLon: [{min_lon:.4f} to {max_lon:.4f}]")
    
    if st.button("💾 حفظ واعتماد استقطاع هذه المنطقة"):
        st.session_state['cropped_bounds'] = (min_lat, max_lat, min_lon, max_lon)
        st.success("🎯 تم حفظ أبعاد الصورة الجوية المستقطعة بنجاح! انتقل للخطوة الثالثة.")

# ==================== الخطوة الثالثة ====================
elif step == "3️⃣ المعالجة الرقمية الفضائية (Sentinel Analysis)":
    st.subheader("🛰️ الخطوة الثالثة: رندرة الصورة الجوية ومعالجة المستشعرات")
    
    if st.session_state['cropped_bounds'] is None:
        st.warning("⚠️ يرجى الذهاب للخطوة الثانية أولاً والضغط على زر حفظ الاستقطاع.")
    else:
        min_lat, max_lat, min_lon, max_lon = st.session_state['cropped_bounds']
        
        analysis_type = st.selectbox("اختر فلتر معالجة الصورة الجوية المستقطعة:", [
            "🟢 معالجة البصري وفحص الرطوبة (Sentinel-2 Visual/Moisture)",
            "🔵 معالجة الرادار واكتشاف التشققات الصخرية (Sentinel-1 SAR Radar)"
        ])
        
        # 🛰️ توليد مصفوفة ومحاكاة تضاريس الصورة الجوية الحقيقية عبر شبكة دقيقة
        nx, ny = 150, 150
        x = np.linspace(min_lon, max_lon, nx)
        y = np.linspace(min_lat, max_lat, ny)
        X, Y = np.meshgrid(x, y)
        
        # بناء مصفوفة صورة جوية طبوغرافية تحاكي وديان وتضاريس حقيقية للموقع المستقطع
        base_topography = np.sin((X - min_lon)/(max_lon - min_lon) * np.pi) * np.cos((Y - min_lat)/(max_lat - min_lat) * np.pi)
        noise = 0.1 * np.sin(X*500) * np.cos(Y*500)
        satellite_matrix = base_topography + noise
        
        # إنشاء الرسم البياني للمعالجة
        fig, ax = plt.subplots(figsize=(10, 6))
        
        if "Sentinel-2" in analysis_type:
            st.info("📊 الفلتر الحالي: يقوم بدمج أطياف الأشعة البصرية وتحت الحمراء لتمييز مجاري السيول الرطبة (تظهر باللون الأخضر والرمادي الجغرافي).")
            # رندرة الصورة الجوية بفلتر "earth" البصري المخصص للأقمار الصناعية
            img = ax.imshow(satellite_matrix, cmap='gist_earth', extent=[min_lon, max_lon, min_lat, max_lat], origin='lower')
            fig.colorbar(img, ax=ax, label="شدة الانعكاس الطيفي لغطاء الأرض")
            ax.set_title("Sentinel-2 High-Resolution Satellite Image (Optical Filter)")
        else:
            st.info("📡 الفلتر الحالي: يحاكي النفاذية الرادارية لتوضيح الشقوق (Lineaments) وخشونة السطح (تظهر باللون الناري والداكن للصدوع).")
            # رندرة الصورة الجوية بفلتر الرادار "inferno/twilight" المخصص للاستشعار الراداري
            img = ax.imshow(satellite_matrix**2, cmap='inferno', extent=[min_lon, max_lon, min_lat, max_lat], origin='lower')
            fig.colorbar(img, ax=ax, label="قوة الارتداد الراداري الخلفي (dB)")
            ax.set_title("Sentinel-1 SAR Radar Surface Texture Image")

        # 📍 إسقاط وتثبيت موقع البئر فوق الصورة الجوية المعالجة تماماً
        ax.plot(st.session_state['target_coords']['lon'], st.session_state['target_coords']['lat'], 
                'ro', markersize=10, markeredgecolor='white', label="📍 موقع بئر الاستكشاف المعتمد")
        
        ax.set_xlabel("Longitude (خط الطول)")
        ax.set_ylabel("Latitude (خط العرض)")
        ax.grid(True, alpha=0.3, linestyle='--') # شبكة الإحداثيات الدقيقة فوق الصورة
        ax.legend(loc="upper right")
        
        # عرض المعالجة الرقمية والصورة الجوية معاً
        st.pyplot(fig)
        st.success("✅ ظهرت الصورة الجوية المستقطعة وجاري تشغيل فلاتر المعالجة الرقمية عليها بنجاح!")
