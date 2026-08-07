import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from scipy.interpolate import griddata
import json

st.set_page_config(page_title="معالج الجاذبية المتقدم والنمذجة 3D", page_icon="🌋", layout="wide")

st.title("🌋 معالج بيانات الجاذبية والنمذجة ثلاثية الأبعاد (3D Gravity Inversion)")
st.caption("وحدة المعالجة الجيوفيزيائية المتقدمة: المشتقات المكانية، الاستخراج الآلي للصدوع، المقطع 2D، والنموذج المجسم 3D")
st.markdown("---")

uploaded_file = st.file_uploader("قم برفع ملف البيانات الجيوفيزيائية (CSV أو XLSX)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    st.success(f"تم تحميل الملف بنجاح! إجمالي عدد نقاط القياس: {len(df)}")

    cols = df.columns.tolist()
    c1, c2, c3 = st.columns(3)
    lon_col = c1.selectbox("خط الطول (Longitude / X):", cols, index=1 if len(cols) > 1 else 0)
    lat_col = c2.selectbox("خط العرض (Latitude / Y):", cols, index=2 if len(cols) > 2 else 0)
    gz_col = c3.selectbox("شذوذ الجاذبية (Residual Gz / Z):", cols, index=3 if len(cols) > 3 else 0)

    # استخراج البيانات وتنظيف الفراغات
    clean_df = df.dropna(subset=[lon_col, lat_col, gz_col])
    x = clean_df[lon_col].values
    y = clean_df[lat_col].values
    z = clean_df[gz_col].values

    # إعادة إنتاج شبكة منتظمة عالية الدقة للتدريج والتضاريس (100x100)
    grid_x, grid_y = np.meshgrid(
        np.linspace(x.min(), x.max(), 100),
        np.linspace(y.min(), y.max(), 100)
    )
    grid_gz = griddata((x, y), z, (grid_x, grid_y), method='cubic')

    # معالجة القيم المفقودة إن وجدت
    if np.isnan(grid_gz).any():
        grid_gz_nearest = griddata((x, y), z, (grid_x, grid_y), method='nearest')
        grid_gz = np.where(np.isnan(grid_gz), grid_gz_nearest, grid_gz)

    # حساب المسافات
    mean_lat_rad = np.radians(y.mean())
    dx = ((x.max() - x.min()) / 100) * 111000 * np.cos(mean_lat_rad)
    dy = ((y.max() - y.min()) / 100) * 111000

    # حساب المشتقات المكانية
    gy, gx = np.gradient(grid_gz, dy, dx)
    thg = np.sqrt(gx**2 + gy**2) * 1000.0

    ny, nx = grid_gz.shape
    kx = 2 * np.pi * np.fft.fftfreq(nx, d=dx)
    ky = 2 * np.pi * np.fft.fftfreq(ny, d=dy)
    KX, KY = np.meshgrid(kx, ky)
    K = np.sqrt(KX**2 + KY**2)

    G_fft = np.fft.fft2(grid_gz)
    fvd = np.real(np.fft.ifft2(K * G_fft)) * 1000.0
    tdr = np.arctan2(fvd, thg)

    # حساب الأعماق الطيفية
    power_spectrum2d = np.abs(G_fft)**2
    k_flat, ps_flat = K.flatten(), power_spectrum2d.flatten()
    k_bins = np.linspace(0, K.max() / 2, 30)
    k_centers = (k_bins[:-1] + k_bins[1:]) / 2
    ps_binned = np.array([np.mean(ps_flat[(k_flat >= k_bins[i]) & (k_flat < k_bins[i + 1])]) for i in range(len(k_bins) - 1)])

    valid = ~np.isnan(ps_binned) & (ps_binned > 0)
    fit_deep = np.polyfit(k_centers[valid][:8], np.log(ps_binned[valid][:8]), 1)
    fit_shallow = np.polyfit(k_centers[valid][8:18], np.log(ps_binned[valid][8:18]), 1)

    deep_depth = abs(-fit_deep[0] / 2.0)
    shallow_depth = abs(-fit_shallow[0] / 2.0)

    # حساب سطح الركيزة مع إبراز التضاريس بدقة (بين -900 م و -1700 م)
    gz_min, gz_max = grid_gz.min(), grid_gz.max()
    gz_norm = (grid_gz - gz_min) / (gz_max - gz_min + 1e-9)
    z_basement_3d = -1700.0 + (gz_norm * 800.0)

    tab1, tab2, tab3, tab4 = st.tabs([
        "1️⃣ الخرائط والتحليل الطيفي",
        "2️⃣ الصدوع وتصدير GIS",
        "3️⃣ المقطع الجيولوجي 2D",
        "4️⃣ النمذجة المجسمة 3D (تفاعلي)"
    ])

    with tab1:
        st.subheader("خرائط المشتقات المكانية لبيانات الجاذبية")
        fig1, axes = plt.subplots(2, 2, figsize=(10, 8), dpi=200)

        im0 = axes[0, 0].contourf(grid_x, grid_y, grid_gz, cmap='RdBu_r')
        axes[0, 0].set_title('Residual Gravity (mGal)')
        fig1.colorbar(im0, ax=axes[0, 0])

        im1 = axes[0, 1].contourf(grid_x, grid_y, thg, cmap='magma')
        axes[0, 1].set_title('Total Horizontal Gradient (THG)')
        fig1.colorbar(im1, ax=axes[0, 1])

        im2 = axes[1, 0].contourf(grid_x, grid_y, fvd, cmap='seismic')
        axes[1, 0].set_title('First Vertical Derivative (FVD)')
        fig1.colorbar(im2, ax=axes[1, 0])

        im3 = axes[1, 1].contourf(grid_x, grid_y, tdr, cmap='coolwarm')
        axes[1, 1].contour(grid_x, grid_y, tdr, levels=[0], colors='black', linestyles='--')
        axes[1, 1].set_title('Tilt Derivative & Contacts (TDR=0)')
        fig1.colorbar(im3, ax=axes[1, 1])

        plt.tight_layout()
        st.pyplot(fig1)

        st.markdown("---")
        st.subheader("نتائج التحليل الطيفي (Depth Estimation)")
        col_a, col_b = st.columns(2)
        col_a.metric("عمق ركيزة القاعدة العميقة (Basement)", f"{deep_depth / 1000.0:.2f} km")
        col_b.metric("عمق التراكيب والصدوع الضحلة", f"{shallow_depth:.0f} m")

    with tab2:
        st.subheader("تتبع الصدوع والتراكيب وتصدير الطبقة الرقمية")
        threshold = st.slider("مستوى حساسية الالتقاط (THG Threshold):", float(thg.min()), float(thg.max()), float(np.percentile(thg, 85)))
        fault_mask = (thg > threshold) & (np.abs(tdr) < 0.25)

        fig2, ax2 = plt.subplots(figsize=(8, 5), dpi=200)
        ax2.contourf(grid_x, grid_y, grid_gz, cmap='gist_earth', alpha=0.6)
        ax2.scatter(grid_x[fault_mask], grid_y[fault_mask], color='red', s=6, label='Extracted Fault Traces')
        ax2.set_xlabel("Longitude (°E)")
        ax2.set_ylabel("Latitude (°N)")
        ax2.legend()
        st.pyplot(fig2)

        features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(lo), float(la)]}}
                    for lo, la in zip(grid_x[fault_mask], grid_y[fault_mask])]
        geojson_str = json.dumps({"type": "FeatureCollection", "features": features})

        st.download_button("💾 تنزيل طبقة الصدوع (GeoJSON جاهز لـ ArcMap/QGIS/Surfer)", geojson_str, "extracted_faults.geojson", "application/json")

    with tab3:
        st.subheader("القطاع الجيولوجي ثنائي الأبعاد (2D Inversion Cross-Section)")
        lat_idx = st.slider("اختر خط العرض للقطاع (Latitude Index):", 0, 99, 50)

        profile_x = grid_x[lat_idx, :]
        profile_gz = grid_gz[lat_idx, :]
        inv_depth = shallow_depth + ((profile_gz - profile_gz.mean()) * 1200.0)

        fig3, ax3 = plt.subplots(figsize=(9, 4), dpi=200)
        ax3_gz = ax3.twinx()
        ax3_gz.plot(profile_x, profile_gz, 'r-', linewidth=2, label='Gz Anomaly (mGal)')
        ax3_gz.set_ylabel('Gravity (mGal)', color='r')

        ax3.fill_between(profile_x, -inv_depth, 0, color='#e6ccb2', label='Sedimentary / Volcanic Cover')
        ax3.fill_between(profile_x, -deep_depth, -inv_depth, color='#7f5539', label='Basement Complex (High Density)')
        ax3.set_xlabel('Longitude (°E)')
        ax3.set_ylabel('Depth (m)')
        ax3.grid(True, linestyle='--', alpha=0.5)
        st.pyplot(fig3)

    # --- Tab 4: النمذجة المجسمة ثلاثية الأبعاد (قابلة للتدوير ومجسمة تضاريسياً) ---
    with tab4:
        st.subheader("3D Subsurface Basement Density Boundary (Inversion Model)")
        st.caption("🔄 يمكنك تدوير المجسم 360 درجة، التكبير/التصغير، وإمالة الزاوية مباشرة بلمس الشاشة")

        # بناء النموذج التفاعلي عبر Plotly باستخدام ألوان Earth مع تضخيم راسي للتضاريس
        fig_3d = go.Figure(data=[
            go.Surface(
                x=grid_x,
                y=grid_y,
                z=z_basement_3d,
                colorscale='Earth',
                colorbar_title='Basement Depth (m)',
                lighting=dict(ambient=0.5, diffuse=0.8, specular=0.3, roughness=0.4, fresnel=0.2),
                contours_z=dict(show=True, usecolormap=True, highlightcolor="white", project_z=False)
            )
        ])

        fig_3d.update_layout(
            title='3D Subsurface Basement Density Boundary (Al-Siyaghi Project Area)',
            autosize=True,
            scene=dict(
                xaxis_title='Longitude (°E)',
                yaxis_title='Latitude (°N)',
                zaxis_title='Depth / Elevation (m)',
                aspectmode='manual',
                aspectratio=dict(x=1, y=1, z=0.65), # إبراز العمق والتضاريس
                camera=dict(
                    eye=dict(x=-1.5, y=-1.5, z=1.1)
                )
            ),
            margin=dict(l=0, r=0, b=0, t=40)
        )

        st.plotly_chart(fig_3d, use_container_width=True)
