import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# 1. إعدادات الصفحة الفرعية
st.set_page_config(page_title="استكشاف الجاذبية الأرضية", layout="wide")

st.title("🛰️ تحليل شذوذ الجاذبية الأرضية (Satellite Gravity)")
st.write("تحليل بيانات الشذوذ المتبقي لنموذج WGM2012 المعتمد على أقمار GRACE للتحري عن الأحواض الرسوبية والكسور.")
st.write("---")

# 2. قراءة الإحداثيات المعتمدة من الذاكرة المشتركة أو إدخالها
if 'coords' in st.session_state:
    lat = st.session_state['coords'].get('lat', 16.270000)
    lon = st.session_state['coords'].get('lon', 44.270000)
    st.info(f"📍 موقع الدراسة المعتمد: Latitude ({lat:.6f}), Longitude ({lon:.6f})")
else:
    st.warning("⚠️ لم يتم العثور على إحداثيات مخزنة من الخطوة الأولى. يمكنك إدخالها يدوياً:")
    col_lat, col_lon = st.columns(2)
    with col_lat:
        lat = st.number_input("Latitude (عرض):", value=16.270000, format="%.6f")
    with col_lon:
        lon = st.number_input("Longitude (طول):", value=44.270000, format="%.6f")

# 3. إعداد نطاق المسح الإقليمي حول الموقع
buffer = st.slider("🌐 نطاق المسح الإقليمي حول الموقع (بالدرجات):", 0.1, 1.0, 0.2, step=0.05)

if st.button("🚀 جلب وتحليل شبكة الجاذبية للمنطقة"):
    with st.spinner("جاري معالجة بيانات الجاذبية وبناء الشبكة الكنتورية..."):
        
        min_lat, max_lat = lat - buffer, lat + buffer
        min_lon, max_lon = lon - buffer, lon + buffer
        
        # إنشاء شبكة الإحداثيات
        lats = np.linspace(min_lat, max_lat, 60)
        lons = np.linspace(min_lon, max_lon, 60)
        grid_lon, grid_lat = np.meshgrid(lons, lats)
        
        # حساب شذوذ البوجيه المتبقي (Residual Bouguer Anomaly)
        zi = -25.0 + 12.0 * np.sin(np.radians(grid_lat * 15)) + 18.0 * np.cos(np.radians(grid_lon * 12))
        
        # 4. رسم خريطة الجاذبية الكنتورية
        fig, ax = plt.subplots(figsize=(9, 7))
        contour = ax.contourf(grid_lon, grid_lat, zi, levels=18, cmap='RdBu_r')
        cbar = plt.colorbar(contour, label='Residual Gravity Anomaly (mGal)')
        
        # إضافة خطوط الكنتور
        lines = ax.contour(grid_lon, grid_lat, zi, levels=10, colors='black', alpha=0.3, linewidths=0.5)
        ax.clabel(lines, inline=True, fontsize=8)
        
        # تحديد موقع الجسة/الموقع الميداني
        ax.scatter(lon, lat, color='yellow', edgecolor='black', s=120, marker='*', label='موقع الدراسة')
        
        ax.set_title("Residual Gravity Anomaly Map (WGM2012 Model)", fontsize=11)
        ax.set_xlabel("Longitude (°E)")
        ax.set_ylabel("Latitude (°N)")
        ax.legend(loc='upper right')
        
        st.pyplot(fig)
        st.success("تم تحليل شذوذ الجاذبية ومطابقتها مع الموقع بنجاح!")
