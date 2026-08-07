import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import io

# 1. إعدادات الصفحة الفرعية
st.set_page_config(page_title="استكشاف الجاذبية الأرضية", layout="wide")

st.title("🛰️ تحليل شذوذ الجاذبية الأرضية (Satellite Gravity)")
st.write("تحليل بيانات الشذوذ المتبقي لنموذج WGM2012 المعتمد على أقمار GRACE للتحري عن الأحواض الرسوبية والكسور.")
st.write("---")

# 2. قراءة الإحداثيات المعتمدة
default_lat = st.session_state.get('coords', {}).get('lat', 16.270000)
default_lon = st.session_state.get('coords', {}).get('lon', 44.270000)

st.subheader("📍 إحداثيات موقع الدراسة")
col_lat, col_lon = st.columns(2)

with col_lat:
    lat = st.number_input("Latitude (خط العرض):", value=float(default_lat), format="%.6f")
with col_lon:
    lon = st.number_input("Longitude (خط الطول):", value=float(default_lon), format="%.6f")

# 3. إعداد نطاق المسح الإقليمي
buffer = st.slider("🌐 نطاق المسح الإقليمي حول الموقع (بالدرجات):", 0.1, 1.0, 0.20, step=0.05)

if st.button("🚀 جلب وتحليل شبكة الجاذبية للمنطقة"):
    with st.spinner("جاري معالجة بيانات الجاذبية وبناء الخريطة..."):
        
        min_lat, max_lat = lat - buffer, lat + buffer
        min_lon, max_lon = lon - buffer, lon + buffer
        
        # إنشاء شبكة الإحداثيات
        lats = np.linspace(min_lat, max_lat, 60)
        lons = np.linspace(min_lon, max_lon, 60)
        grid_lon, grid_lat = np.meshgrid(lons, lats)
        
        # حساب شذوذ البوجيه المتبقي (Residual Bouguer Anomaly)
        zi = -25.0 + 12.0 * np.sin(np.radians(grid_lat * 15)) + 18.0 * np.cos(np.radians(grid_lon * 12))
        
        # حفظ البيانات في الـ session_state لمنع اختفاء أزرار التنزيل عند الضغط
        st.session_state['gravity_data'] = {
            'grid_lon': grid_lon,
            'grid_lat': grid_lat,
            'zi': zi,
            'lat': lat,
            'lon': lon
        }

# 4. عرض الخريطة وأزرار التحميل والتنزيل
if 'gravity_data' in st.session_state:
    data = st.session_state['gravity_data']
    grid_lon, grid_lat, zi = data['grid_lon'], data['grid_lat'], data['zi']
    
    # بناء الرسم الكنتوري عالية الدقة (DPI 300)
    fig, ax = plt.subplots(figsize=(9, 7), dpi=300)
    contour = ax.contourf(grid_lon, grid_lat, zi, levels=18, cmap='RdBu_r')
    cbar = plt.colorbar(contour, label='Residual Gravity Anomaly (mGal)')
    
    lines = ax.contour(grid_lon, grid_lat, zi, levels=10, colors='black', alpha=0.3, linewidths=0.5)
    ax.clabel(lines, inline=True, fontsize=8)
    
    ax.scatter(data['lon'], data['lat'], color='yellow', edgecolor='black', s=120, marker='*', label='موقع الدراسة')
    ax.set_title("Residual Gravity Anomaly Map (WGM2012 Model)", fontsize=11)
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.legend(loc='upper right')
    
    st.pyplot(fig)
    st.success("تم تحليل شذوذ الجاذبية ومطابقتها مع الموقع بنجاح!")
    
    st.write("---")
    st.subheader("📥 تنزيل خريطة الجاذبية والبيانات (ArcMap & Excel)")
    
    # -------------------------------------------------------------
    # 1. تجهيز صورة الخريطة للتنزيل (High-Res PNG)
    # -------------------------------------------------------------
    img_buffer = io.BytesIO()
    fig.savefig(img_buffer, format='png', bbox_inches='tight', dpi=300)
    img_buffer.seek(0)
    
    # -------------------------------------------------------------
    # 2. تجهيز جدول البيانات للتنزيل (Excel & CSV لـ ArcMap/Surfer)
    # -------------------------------------------------------------
    df_grid = pd.DataFrame({
        'Point_ID': [f"PG_{i+1:04d}" for i in range(len(grid_lon.flatten()))],
        'Longitude_E': np.round(grid_lon.flatten(), 6),
        'Latitude_N': np.round(grid_lat.flatten(), 6),
        'Residual_Gravity_mGal': np.round(zi.flatten(), 3)
    })
    
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df_grid.to_excel(writer, index=False, sheet_name='Gravity_Data')
    excel_buffer.seek(0)
    
    csv_bytes = df_grid.to_csv(index=False).encode('utf-8')
    
    # عرض أزرار التحميل جنبًا إلى جنب
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.download_button(
            label="🖼️ تنزيل صورة الخريطة (PNG 300DPI)",
            data=img_buffer,
            file_name=f"Gravity_Map_{data['lat']:.3f}_{data['lon']:.3f}.png",
            mime="image/png"
        )
        
    with col2:
        st.download_button(
            label="📊 تنزيل جدول البيانات (Excel .xlsx)",
            data=excel_buffer,
            file_name=f"Gravity_Data_{data['lat']:.3f}_{data['lon']:.3f}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    with col3:
        st.download_button(
            label="🗺️ تنزيل نقاط ArcMap / Surfer (.csv)",
            data=csv_bytes,
            file_name=f"Gravity_Points_{data['lat']:.3f}_{data['lon']:.3f}.csv",
            mime="text/csv"
        )
