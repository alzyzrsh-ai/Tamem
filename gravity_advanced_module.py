import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from scipy.ndimage import gaussian_filter

st.set_page_config(page_title="المعالج الجيوفيزيائي المتقدم للجاذبية", layout="wide")

st.title("🌋 وحدة المعالجة والتفسير التلقائي المتقدمة لبيانات الجاذبية")
st.markdown("---")

# 1. رفع الملفات
uploaded_file = st.file_uploader("قم برفع ملف البيانات (CSV أو XLSX)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    # قراءة البيانات
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
        
    st.success(f"تم تحميل الملف بنجاح! عدد النقاط: {len(df)}")
    
    # اختيار الأعمدة
    cols = df.columns.tolist()
    c1, c2, c3 = st.columns(3)
    lon_col = c1.selectbox("عمود خط الطول (Longitude / X):", cols, index=1 if len(cols)>1 else 0)
    lat_col = c2.selectbox("عمود خط العرض (Latitude / Y):", cols, index=2 if len(cols)>2 else 0)
    gz_col = c3.selectbox("عمود شذوذ الجاذبية (Gravity / Z):", cols, index=3 if len(cols)>3 else 0)
    
    # تجهيز الشبكة (Grid Generation)
    lons = np.sort(df[lon_col].unique())
    lats = np.sort(df[lat_col].unique())
    grid_lon, grid_lat = np.meshgrid(lons, lats)
    grid_gz = df.pivot(index=lat_col, columns=lon_col, values=gz_col).values
    
    # مسافات الشبكة بالمتر
    mean_lat_rad = np.radians(df[lat_col].mean())
    dx = (lons[1] - lons[0]) * 111000 * np.cos(mean_lat_rad)
    dy = (lats[1] - lats[0]) * 111000
    
    # حساب المشتقات المكانية
    gy, gx = np.gradient(grid_gz, dy, dx)
    thg = np.sqrt(gx**2 + gy**2) * 1000.0  # mGal/km
    
    # المشتقة الرأسية الأولى عبر FFT
    ny, nx = grid_gz.shape
    kx = 2 * np.pi * np.fft.fftfreq(nx, d=dx)
    ky = 2 * np.pi * np.fft.fftfreq(ny, d=dy)
    KX, KY = np.meshgrid(kx, ky)
    K = np.sqrt(KX**2 + KY**2)
    
    G_fft = np.fft.fft2(grid_gz)
    fvd = np.real(np.fft.ifft2(K * G_fft)) * 1000.0  # mGal/km
    tdr = np.arctan2(fvd, thg)  # Tilt Derivative in radians
    
    # تبويب المحاور الثلاثة
    tab1, tab2, tab3 = st.tabs([
        "1️⃣ المشتقات المكانية والتحليل الطيفي", 
        "2️⃣ استخراج الصدوع وتصدير Shapefile", 
        "3️⃣ القطاع الجيولوجي والنمذجة العكسية (2D Inversion)"
    ])
    
    # --- المكون الأول: المشتقات المكانية والتحليل الطيفي ---
    with tab1:
        st.subheader("خرائط المشتقات الجيوفيزيائية (Derivative Maps)")
        
        fig1, axes = plt.subplots(2, 2, figsize=(12, 10), dpi=200)
        
        # Gz
        c1 = axes[0, 0].contourf(grid_lon, grid_lat, grid_gz, levels=20, cmap='RdBu_r')
        fig1.colorbar(c1, ax=axes[0, 0], label='Residual Gz (mGal)')
        axes[0, 0].set_title('A) Residual Gravity Anomaly')
        
        # THG
        c2 = axes[0, 1].contourf(grid_lon, grid_lat, thg, levels=20, cmap='magma')
        fig1.colorbar(c2, ax=axes[0, 1], label='THG (mGal/km)')
        axes[0, 1].set_title('B) Total Horizontal Gradient (THG)')
        
        # FVD
        c3 = axes[1, 0].contourf(grid_lon, grid_lat, fvd, levels=20, cmap='seismic')
        fig1.colorbar(c3, ax=axes[1, 0], label='FVD (mGal/km)')
        axes[1, 0].set_title('C) First Vertical Derivative (FVD)')
        
        # TDR
        c4 = axes[1, 1].contourf(grid_lon, grid_lat, tdr, levels=20, cmap='coolwarm')
        axes[1, 1].contour(grid_lon, grid_lat, tdr, levels=[0], colors='black', linewidths=1.5, linestyles='--')
        fig1.colorbar(c4, ax=axes[1, 1], label='TDR (rad)')
        axes[1, 1].set_title('D) Tilt Derivative (TDR) & Zero Contour (Fault Contacts)')
        
        plt.tight_layout()
        st.pyplot(fig1)
        
        # التحليل الطيفي لتقدير الأعماق
        st.markdown("---")
        st.subheader("التحليل الطيفي وحساب أعماق المصادر (Power Spectrum Depth Estimation)")
        
        power_spectrum2d = np.abs(G_fft)**2
        k_flat = K.flatten()
        ps_flat = power_spectrum2d.flatten()
        
        k_bins = np.linspace(0, K.max()/2, 30)
        k_centers = (k_bins[:-1] + k_bins[1:]) / 2
        ps_binned = [np.mean(ps_flat[(k_flat >= k_bins[i]) & (k_flat < k_bins[i+1])]) for i in range(len(k_bins)-1)]
        
        ps_binned = np.array(ps_binned)
        valid = ~np.isnan(ps_binned) & (ps_binned > 0)
        k_v, log_ps_v = k_centers[valid], np.log(ps_binned[valid])
        
        fit_deep = np.polyfit(k_v[:8], log_ps_v[:8], 1)
        fit_shallow = np.polyfit(k_v[8:18], log_ps_v[8:18], 1)
        
        depth_deep = -fit_deep[0] / 2.0
        depth_shallow = -fit_shallow[0] / 2.0
        
        col_d1, col_d2 = st.columns(2)
        col_d1.metric("عمق صخور الركيزة العميقة (Basement Depth)", f"{depth_deep/1000.0:.2f} km")
        col_d2.metric("عمق الصدوع والتركيبات الضحلة (Faults Depth)", f"{depth_shallow:.0f} meters")

    # --- المكون الثاني: استخراج الصدوع تلقائياً وتصديرها ---
    with tab2:
        st.subheader("تتبع الصدوع التلقائي وتصدير الطبقات الرقمية")
        
        threshold = st.slider("مستوى حساسية التقاط الصدوع (THG Threshold):", float(thg.min()), float(thg.max()), float(np.percentile(thg, 85)))
        
        # استخراج محاور الصدوع
        fault_mask = (thg > threshold) & (np.abs(tdr) < 0.2)
        
        fig2, ax2 = plt.subplots(figsize=(8, 6), dpi=200)
        ax2.contourf(grid_lon, grid_lat, grid_gz, levels=15, cmap='gist_earth', alpha=0.6)
        ax2.scatter(grid_lon[fault_mask], grid_lat[fault_mask], color='red', s=5, label='Extracted Fault / Contact Points')
        ax2.set_title("Extracted Fault Traces Overlaid on Gravity Map")
        ax2.set_xlabel("Longitude (°E)")
        ax2.set_ylabel("Latitude (°N)")
        ax2.legend()
        st.pyplot(fig2)
        
        # بناء ملف GeoJSON جاهز للتنزيل لـ ArcMap/QGIS
        features = []
        f_lons = grid_lon[fault_mask]
        f_lats = grid_lat[fault_mask]
        
        for lo, la in zip(f_lons, f_lats):
            feat = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lo), float(la)]},
                "properties": {"type": "Fault_Trace"}
            }
            features.append(feat)
            
        geojson_data = {"type": "FeatureCollection", "features": features}
        geojson_str = json.dumps(geojson_data)
        
        st.download_button(
            label="💾 تنزيل طبقة الصدوع بفرمت (GeoJSON / GIS Format)",
            data=geojson_str,
            file_name="extracted_faults.geojson",
            mime="application/json"
        )

    # --- المكون الثالث: القطاع الجيولوجي والنمذجة العكسية 2D ---
    with tab3:
        st.subheader("رسم المقطع الجيولوجي والنمذجة العكسية (2D Inversion Profile)")
        
        selected_lat_idx = st.slider("اختر خط العرض للقطاع (Latitude Profile Index):", 0, len(lats)-1, len(lats)//2)
        
        profile_x = lons
        profile_gz = grid_gz[selected_lat_idx, :]
        profile_lat = lats[selected_lat_idx]
        
        # النمذجة العكسية التقديرية لسطح الركيزة (2D Inversion)
        # Depth = Base_Depth - (Gz - Mean_Gz) * Scale
        scaled_gz = (profile_gz - profile_gz.mean())
        inverted_basement_depth = depth_shallow + (scaled_gz * 1500.0)
        
        fig3, ax3 = plt.subplots(figsize=(10, 5), dpi=200)
        
        # رسم المنحنى
        ax3_gz = ax3.twinx()
        ax3_gz.plot(profile_x, profile_gz, 'r-', linewidth=2, label='Gravity Anomaly (mGal)')
        ax3_gz.set_ylabel('Gravity Anomaly (mGal)', color='r')
        
        # رسم المقطع الجيولوجي
        topo_surface = np.zeros_like(profile_x)
        ax3.fill_between(profile_x, -inverted_basement_depth, topo_surface, color='#e6ccb2', label='Sedimentary / Volcanic Cover')
        ax3.fill_between(profile_x, -depth_deep, -inverted_basement_depth, color='#7f5539', label='Basement Complex (High Density)')
        
        ax3.set_title(f'2D Subsurface Density Profile along Latitude {profile_lat:.4f}°N')
        ax3.set_xlabel('Longitude (°E)')
        ax3.set_ylabel('Depth below Surface (m)')
        ax3.set_ylim(-depth_deep*0.3, 200)
        ax3.grid(True, linestyle='--', alpha=0.5)
        
        st.pyplot(fig3)

