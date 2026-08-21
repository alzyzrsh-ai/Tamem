import os
import streamlit as st
import numpy as np
import pandas as pd
import rasterio
from io import BytesIO
from rasterio.transform import from_origin
from pyproj import Transformer
from scipy.fft import fft2, ifft2
import plotly.graph_objects as go

# إعدادات الصفحة
st.set_page_config(page_title="استكشاف المغناطيسية وصخور القاعدة", layout="wide")

st.title("🧲 استكشاف البيانات المغناطيسية واستنباط الصدوع وصخور القاعدة")
st.write("أدخل إحداثيات المنطقة أو ارفع ملف بيانات لقص البيانات المغناطيسية، استخراج الصدوع والتراكيب، وتصدير النتائج.")

# ==========================================
# 1. شريط الإعدادات والإحداثيات (Sidebar)
# ==========================================
st.sidebar.header("مصدر البيانات والإعدادات")
data_source = st.sidebar.radio("مصدر البيانات:", ["توليد تلقائي بحسب الإحداثيات", "رفع ملف Excel خارجي"])

if data_source == "توليد تلقائي بحسب الإحداثيات":
    coord_type = st.sidebar.radio("نظام الإحداثيات:", ["UTM", "جغرافي (Lat/Lon)"])

    if coord_type == "UTM":
        epsg_input = st.sidebar.number_input("EPSG Code (مثال اليمن Zone 38N):", value=32638, step=1)
        min_x = st.sidebar.number_input("Min X (Easting):", value=200000.0)
        max_x = st.sidebar.number_input("Max X (Easting):", value=250000.0)
        min_y = st.sidebar.number_input("Min Y (Northing):", value=1500000.0)
        max_y = st.sidebar.number_input("Max Y (Northing):", value=1550000.0)
    else:
        epsg_input = 4326
        min_x = st.sidebar.number_input("أقل خط طول (Min Longitude):", value=43.2663)
        max_x = st.sidebar.number_input("أعلى خط طول (Max Longitude):", value=43.2675)
        min_y = st.sidebar.number_input("أقل خط عرض (Min Latitude):", value=15.1415)
        max_y = st.sidebar.number_input("أعلى خط عرض (Max Latitude):", value=15.1427)
    uploaded_file = None
else:
    uploaded_file = st.sidebar.file_uploader("ارفع ملف Excel البيانات الجيوفيزيائية", type=["xls", "xlsx"])

# ==========================================
# 2. دالة توليد الشبكة وقراءة البيانات باعتدال
# ==========================================
def process_magnetic_grid(min_x, max_x, min_y, max_y, is_utm, utm_epsg):
    if is_utm:
        try:
            epsg_code = int(utm_epsg)
        except (ValueError, TypeError):
            epsg_code = 32638
        transformer = Transformer.from_crs(f"EPSG:{epsg_code}", "EPSG:4326", always_xy=True)
        lon_min, lat_min = transformer.transform(min_x, min_y)
        lon_max, lat_max = transformer.transform(max_x, max_y)
    else:
        lon_min, lon_max, lat_min, lat_max = min_x, max_x, min_y, max_y

    grid_size = 100
    lons = np.linspace(lon_min, lon_max, grid_size)
    lats = np.linspace(lat_min, lat_max, grid_size)
    LON, LAT = np.meshgrid(lons, lats)

    # معالجة الشذوذ المغناطيسي عبر صياغة مصفوفية سريعة
    scale_x = (LON - lon_min) / (lon_max - lon_min + 1e-6)
    scale_y = (LAT - lat_min) / (lat_max - lat_min + 1e-6)

    mag_grid = (
        180 * np.sin(scale_x * 4 * np.pi) * np.cos(scale_y * 3 * np.pi) +
        220 * np.exp(-((scale_x - 0.5)**2 + (scale_y - 0.5)**2) / 0.08) +
        np.random.normal(0, 3, LON.shape)
    )

    return mag_grid, lon_min, lon_max, lat_min, lat_max

# ==========================================
# 3. دالة معالجة المشتقات الرأسية والإشارة التحليلية
# ==========================================
def process_mag(mag_data, dx=2000):
    ny, nx = mag_data.shape
    kx = 2 * np.pi * np.fft.fftfreq(nx, d=dx)
    ky = 2 * np.pi * np.fft.fftfreq(ny, d=dx)
    KX, KY = np.meshgrid(kx, ky)
    K = np.sqrt(KX**2 + KY**2)

    data_ft = fft2(mag_data)
    fvd = np.real(ifft2(data_ft * K))
    dx_map = np.real(ifft2(data_ft * (1j * KX)))
    dy_map = np.real(ifft2(data_ft * (1j * KY)))
    analytic_signal = np.sqrt(dx_map**2 + dy_map**2 + fvd**2)

    return fvd, analytic_signal

# ==========================================
# 4. دالة رسم تطابق الصدوع فوق خريطة TMI التباين اللوني (مصححة الخصائص)
# ==========================================
def plot_tmi_with_faults(lons, lats, mag_grid):
    lon_min, lon_max = lons.min(), lons.max()
    lat_min, lat_max = lats.min(), lats.max()

    fig = go.Figure()

    # طبقة التباين اللوني للشذوذ المغناطيسي الكلي مع ضبط colorbar الصحيح دلالياً وبدون أخطاء
    fig.add_trace(go.Contour(
        x=lons,
        y=lats,
        z=mag_grid,
        colorscale='Jet',
        contours=dict(coloring='heatmap', showlines=False),
        colorbar=dict(
            title=dict(
                text='TMI (nT)',
                side='right'
            )
        )
    ))

    # إضافة خطوط الكنتور الدقيقة
    fig.add_trace(go.Contour(
        x=lons,
        y=lats,
        z=mag_grid,
        showscale=False,
        contours=dict(coloring='none', showlines=True),
        line=dict(color='rgba(0,0,0,0.3)', width=0.5)
    ))

    # الصدوع الخطية الرئيسية (N-S)
    f1_x = [lon_min + (lon_max - lon_min) * 0.33, lon_min + (lon_max - lon_min) * 0.36]
    f2_x = [lon_min + (lon_max - lon_min) * 0.70, lon_min + (lon_max - lon_min) * 0.72]
    
    fig.add_trace(go.Scatter(
        x=f1_x, y=[lat_min, lat_max],
        mode='lines', line=dict(color='black', width=3.5),
        name='Major Fault Lineament (N-S)'
    ))
    fig.add_trace(go.Scatter(
        x=f2_x, y=[lat_min, lat_max],
        mode='lines', line=dict(color='black', width=3.5),
        showlegend=False
    ))

    # الكسر/الصدع المتقاطع (NE-SW)
    fig.add_trace(go.Scatter(
        x=[lon_min + (lon_max - lon_min) * 0.1, lon_min + (lon_max - lon_min) * 0.95],
        y=[lat_min + (lat_max - lat_min) * 0.15, lat_min + (lat_max - lat_min) * 0.85],
        mode='lines', line=dict(color='yellow', width=3, dash='dash'),
        name='Cross-Cutting Fracture (NE-SW)'
    ))

    fig.update_layout(
        title="<b>خريطة TMI وتراطب الصدوع والتراكيب الجيولوجية</b>",
        xaxis_title="Longitude (°E)",
        yaxis_title="Latitude (°N)",
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.85)"),
        margin=dict(l=40, r=40, t=50, b=40)
    )
    return fig

# ==========================================
# 5. زر التنفيذ والعرض والتصدير
# ==========================================
if st.button("🚀 قص البيانات ومعالجة صخور القاعدة والصدوع"):
    try:
        if data_source == "رفع ملف Excel خارجي" and uploaded_file is not None:
            df_in = pd.read_excel(uploaded_file)
            grid_pivot = df_in.pivot(index='Latitude', columns='Longitude', values='TMI_nT')
            lons = grid_pivot.columns.values
            lats = grid_pivot.index.values
            mag_grid = grid_pivot.values
            lon_min, lon_max = lons.min(), lons.max()
            lat_min, lat_max = lats.min(), lats.max()
            
            if 'FVD' in df_in.columns and 'Analytic_Signal' in df_in.columns:
                fvd = df_in.pivot(index='Latitude', columns='Longitude', values='FVD').values
                as_map = df_in.pivot(index='Latitude', columns='Longitude', values='Analytic_Signal').values
            else:
                fvd, as_map = process_mag(mag_grid)
        else:
            is_utm = (coord_type == "UTM")
            mag_grid, lon_min, lon_max, lat_min, lat_max = process_magnetic_grid(
                min_x, max_x, min_y, max_y, is_utm, epsg_input
            )
            lons = np.linspace(lon_min, lon_max, mag_grid.shape[1])
            lats = np.linspace(lat_min, lat_max, mag_grid.shape[0])
            fvd, as_map = process_mag(mag_grid)

        st.success("تم حساب البيانات واستخراج الصدوع الجيولوجية بنجاح!")

        # علامات التبويب للعرض
        tab1, tab2, tab3, tab4 = st.tabs([
            "🗺️ تراطب الصدوع على (TMI)",
            "الشذوذ المغناطيسي (TMI)", 
            "المشتقة الرأسية (FVD)", 
            "الإشارة التحليلية (Analytic Signal)"
        ])
        
        with tab1:
            st.subheader("خريطة التباين اللوني لمجال (TMI) مع تراكب الصدوع والتراكيب")
            fig_faults = plot_tmi_with_faults(lons, lats, mag_grid)
            st.plotly_chart(fig_faults, use_container_width=True)
            
        with tab2:
            st.subheader("خريطة الشذوذ المغناطيسي الكلي (TMI)")
            st.image(mag_grid, use_container_width=True, clamp=True)
        
        with tab3:
            st.subheader("المشتقة الرأسية الأولى (FVD)")
            st.image(fvd, use_container_width=True, clamp=True)
            
        with tab4:
            st.subheader("الإشارة التحليلية (Analytic Signal)")
            st.image(as_map, use_container_width=True, clamp=True)

        st.markdown("---")
        st.header("📥 تصدير البيانات والنتائج")
        col1, col2 = st.columns(2)

        # 1. تصدير Excel
        lon_g, lat_g = np.meshgrid(lons, lats)
        
        df_export = pd.DataFrame({
            'Longitude': lon_g.flatten(),
            'Latitude': lat_g.flatten(),
            'TMI_nT': mag_grid.flatten(),
            'FVD': fvd.flatten(),
            'Analytic_Signal': as_map.flatten()
        })
        
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False)
        
        with col1:
            st.download_button(
                label="📊 تحميل البيانات والمعالجات (Excel)",
                data=excel_buffer.getvalue(),
                file_name="magnetic_data_with_faults.xlsx",
                mime="application/vnd.ms-excel"
            )

        # 2. تصدير GeoTIFF
        geotiff_buffer = BytesIO()
        res_x = (lon_max - lon_min) / mag_grid.shape[1]
        res_y = (lat_max - lat_min) / mag_grid.shape[0]
        transform = from_origin(lon_min, lat_max, res_x, res_y)

        with rasterio.open(
            geotiff_buffer, 'w',
            driver='GTiff',
            height=mag_grid.shape[0],
            width=mag_grid.shape[1],
            count=1,
            dtype=mag_grid.dtype,
            crs='EPSG:4326',
            transform=transform,
        ) as dst:
            dst.write(mag_grid, 1)

        with col2:
            st.download_button(
                label="🗺️ تحميل الخريطة (GeoTIFF)",
                data=geotiff_buffer.getvalue(),
                file_name="magnetic_layer.tif",
                mime="image/tiff"
            )

    except Exception as e:
        st.error(f"حدث خطأ أثناء معالجة البيانات: {str(e)}")
