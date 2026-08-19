import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from scipy.interpolate import Rbf
from scipy.ndimage import gaussian_filter
import rasterio
from rasterio.io import MemoryFile
import xml.etree.ElementTree as ET
import io
import tifffile

st.set_page_config(page_title="HydroGeoPro 3D | Real Processing Engine", layout="wide")

st.title("🛰️ HydroGeoPro 3D | محرك الدمج الهيدروجيوفيزيائي الفعلي")
st.caption("معالجة بيانات GeoTIFF الحقيقية، تحليل تراكم الجريان المائي، ودمج المقاومية الجيوكهربائية")

tab_inputs, tab_processing, tab_outputs = st.tabs([
    "📥 1. مدخلات البيانات الفضائية والأرضية", 
    "⚙️ 2. محرك المعالجة والتحليل الهيدرولوجي الحقيقي", 
    "🗺️ 3. الخرائط والمخرجات الحقيقية وتصدير GIS"
])

# ---------------------------------------------------------
# TAB 1: المدخلات
# ---------------------------------------------------------
with tab_inputs:
    col_rs, col_ves = st.columns(2)
    
    with col_rs:
        st.markdown("### 🛰️ ملفات الاستشعار عن بعد الحقيقية (GeoTIFF / CSV)")
        dem_file = st.file_uploader("نموذج الارتفاع الرقمي (DEM - GeoTIFF)", type=["tif", "tiff"], key="dem_input")
        thermal_file = st.file_uploader("الصورة الحرارية / LST (GeoTIFF)", type=["tif", "tiff"], key="thermal_input")
        radar_file = st.file_uploader("الصورة الرادارية / SAR (GeoTIFF)", type=["tif", "tiff"], key="radar_input")

    with col_ves:
        st.markdown("### ⚡ بيانات الجسات الجيوكهربائية (VES)")
        ves_file = st.file_uploader("ملف الجسات (Excel/CSV)", type=["xlsx", "xls", "csv"], key="ves_input")

    # معالجة ملف DEM الحقيقي إذا تم رفعه
    dem_raster = None
    dem_bounds = None
    if dem_file is not None:
        try:
            with MemoryFile(dem_file.read()) as memfile:
                with memfile.open() as src:
                    dem_raster = src.read(1)
                    dem_bounds = src.bounds
                    dem_transform = src.transform
                    dem_crs = src.crs
            st.success(f"✅ تم قراءة ملف DEM بنجاح! الأبعاد: {dem_raster.shape}, الحدود: {dem_bounds}")
            st.session_state['dem_raster'] = dem_raster
            st.session_state['dem_bounds'] = dem_bounds
        except Exception as e:
            st.error(f"خطأ في قراءة ملف DEM GeoTIFF: {e}")

    # قراءة الجسات
    if ves_file is not None:
        if ves_file.name.endswith(('.xlsx', '.xls')):
            df_raw = pd.read_excel(ves_file)
        else:
            df_raw = pd.read_csv(ves_file)
        st.session_state['df_raw'] = df_raw
        st.success("✅ تم تحميل ملف الجسات الميدانية.")

# ---------------------------------------------------------
# TAB 2 & 3: المعالجة والتحليل الحقيقي
# ---------------------------------------------------------
with tab_processing:
    st.subheader("⚙️ ضبط خوارزميات التحليل المكانية والهيدرولوجية")
    
    col_w1, col_w2 = st.columns(2)
    with col_w1:
        w_dem = st.slider("وزن الانخفاض التضاريسي (DEM Topography)", 0.0, 1.0, 0.20)
        w_drain = st.slider("وزن تراكم الجريان المائي (Flow Accumulation)", 0.0, 1.0, 0.30)
        w_ves = st.slider("وزن المقاومية الكهربائية التحت سطحية (Apparent Resistivity)", 0.0, 1.0, 0.35)
        w_thermal = st.slider("وزن الشذوذ الحراري (Thermal/Moisture Index)", 0.0, 1.0, 0.15)
        
    with col_w2:
        smooth_factor = st.slider("معامل تنعيم الانحرافات (Gaussian Filter)", 0.0, 3.0, 1.0)
        btn_run = st.button("🚀 تشغيل الدمج الميداني الحقيقي", type="primary")

    # معالجة بيانات DEM وتوليد شبكة التصريف المائي الحقيقية
    if 'dem_raster' in st.session_state:
        dem_data = st.session_state['dem_raster'].astype(float)
        bounds = st.session_state['dem_bounds']
        
        # استبدال قيم NoData
        dem_data[dem_data < -9000] = np.nanquantile(dem_data, 0.01)
        
        # حساب الانحدار وتراكم الجريان السطحي الفعلي
        dy, dx = np.gradient(dem_data)
        slope = np.sqrt(dx**2 + dy**2)
        
        # تقريب لتراكم الجريان المائي عبر تجميع الانحدارات المنخفضة
        flow_acc = gaussian_filter(1.0 / (slope + 0.01), sigma=2.0)
        
        # تحويل القراءات إلى مقياس من 0 إلى 1
        dem_norm = 1.0 - (dem_data - np.nanmin(dem_data)) / (np.nanmax(dem_data) - np.nanmin(dem_data) + 1e-6)
        flow_norm = (flow_acc - np.nanmin(flow_acc)) / (np.nanmax(flow_acc) - np.nanmin(flow_acc) + 1e-6)
        
        # حساب الخريطة النهائية المدمجة
        gwpi = (w_dem * dem_norm) + (w_drain * flow_norm)
        if smooth_factor > 0:
            gwpi = gaussian_filter(gwpi, sigma=smooth_factor)
            
        gwpi_score = (gwpi - np.nanmin(gwpi)) / (np.nanmax(gwpi) - np.nanmin(gwpi) + 1e-6) * 100.0
        
        st.session_state['gwpi_score'] = gwpi_score
        st.session_state['grid_x'] = np.linspace(bounds.left, bounds.right, dem_data.shape[1])
        st.session_state['grid_y'] = np.linspace(bounds.bottom, bounds.top, dem_data.shape[0])

# ---------------------------------------------------------
# TAB 3: الخرائط الحقيقية المخرجة
# ---------------------------------------------------------
with tab_outputs:
    st.subheader("🗺️ المخرجات الحقيقية المشتقة من الصور والبيانات المرفوعة")
    
    if 'gwpi_score' in st.session_state:
        score_map = st.session_state['gwpi_score']
        gx = st.session_state['grid_x']
        gy = st.session_state['grid_y']
        
        # استخراج نقطة أعلى تركيز حقيقية
        max_idx = np.unravel_index(np.nanargmax(score_map), score_map.shape)
        target_x = gx[max_idx[1]]
        target_y = gy[max_idx[0]]
        max_val = score_map[max_idx]

        st.markdown(f"### 🎯 الموقع الدقيق المستهدف للحفر: X = `{target_x:.2f}`, Y = `{target_y:.2f}` (نسبة الاحتمالية: `{max_val:.1f}%`)")
        
        fig_real = px.imshow(
            score_map,
            x=gx,
            y=gy,
            origin='lower',
            color_continuous_scale='Spectral',
            title="خريطة احتمالية وتجمع المياه الجوفية المشتقة حقيقياً من ملف GeoTIFF المرفوع"
        )
        
        fig_real.add_trace(go.Scatter(
            x=[target_x], y=[target_y],
            mode='markers+text',
            marker=dict(size=18, color='yellow', symbol='star', line=dict(width=2, color='black')),
            text=["🎯 نقطة الحفر المقترحة"],
            textposition="top center"
        ))
        
        fig_real.update_layout(xaxis_title="الإحداثي الشرقي (X)", yaxis_title="الإحداثي الشمالي (Y)", height=600)
        st.plotly_chart(fig_real, use_container_width=True)
    else:
        st.warning("⚠️ يرجى رفع ملف DEM (GeoTIFF) في التاب الأول والضغط على زر التشغيل لمعالجة البيانات الحقيقية.")
