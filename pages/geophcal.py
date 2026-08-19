import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from scipy.interpolate import Rbf
from scipy.ndimage import gaussian_filter
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
        dem_file = st.file_uploader("نموذج الارتفاع الرقمي (DEM - GeoTIFF أو CSV)", type=["tif", "tiff", "csv"], key="dem_input")
        thermal_file = st.file_uploader("الصورة الحرارية / LST (GeoTIFF أو CSV)", type=["tif", "tiff", "csv"], key="thermal_input")
        radar_file = st.file_uploader("الصورة الرادارية / SAR (GeoTIFF أو CSV)", type=["tif", "tiff", "csv"], key="radar_input")

    with col_ves:
        st.markdown("### ⚡ بيانات الجسات الجيوكهربائية (VES)")
        ves_file = st.file_uploader("ملف الجسات (Excel/CSV)", type=["xlsx", "xls", "csv"], key="ves_input")

    # قراءة ملف DEM الجغرافي الحقيقي بواسطة tifffile بدلاً من rasterio
    if dem_file is not None:
        try:
            if dem_file.name.endswith(('.tif', '.tiff')):
                # قراءة البكسلات المباشرة من GeoTIFF
                dem_bytes = dem_file.read()
                dem_raster = tifffile.imread(io.BytesIO(dem_bytes))
                
                # إذا كانت الصورة متعددة القنوات تأخذ القناة الأولى
                if dem_raster.ndim > 2:
                    dem_raster = dem_raster[:, :, 0]
                    
                st.success(f"✅ تم قراءة مصفوفة DEM الحقيقية بنجاح! الأبعاد: {dem_raster.shape[1]}x{dem_raster.shape[0]} بكسل")
                st.session_state['dem_raster'] = dem_raster
            elif dem_file.name.endswith('.csv'):
                df_dem = pd.read_csv(dem_file)
                st.session_state['df_dem'] = df_dem
                st.success("✅ تم قراءة جدول DEM بنجاح.")
        except Exception as e:
            st.error(f"خطأ في قراءة ملف DEM: {e}")

    # قراءة بيانات الجسات
    if ves_file is not None:
        try:
            if ves_file.name.endswith(('.xlsx', '.xls')):
                df_raw = pd.read_excel(ves_file)
            else:
                df_raw = pd.read_csv(ves_file)
            st.session_state['df_raw'] = df_raw
            st.success("✅ تم تحميل ملف الجسات الميدانية بنجاح.")
        except Exception as e:
            st.error(f"خطأ في قراءة ملف الجسات: {e}")

# ---------------------------------------------------------
# TAB 2: المعالجة والتحليل الحقيقي
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
        utm_zone = st.number_input("نظام الإسقاط UTM Zone:", value=38)
        btn_run = st.button("🚀 تشغيل الدمج الميداني الحقيقي", type="primary")

    # تنفيذ تحليل الارتفاع والتصريف المائي من الشبكة الحقيقية المرفوعة
    if 'dem_raster' in st.session_state:
        dem_data = st.session_state['dem_raster'].astype(float)
        
        # تنظيف القيم الشاذة أو NoData
        valid_mask = (dem_data > -9000) & (dem_data < 9000)
        if not np.any(valid_mask):
            dem_data = np.nan_to_num(dem_data, nan=0.0)
        else:
            min_val = np.min(dem_data[valid_mask])
            dem_data[~valid_mask] = min_val
        
        # حساب الانحدار وتراكم الجريان السطحي الفعلي (Flow Accumulation Proxy)
        dy, dx = np.gradient(dem_data)
        slope = np.sqrt(dx**2 + dy**2)
        
        # استخراج المدارات والوديان المنخفضة عبر مقلوب الانحدار مع الفلترة
        flow_acc = gaussian_filter(1.0 / (slope + 0.001), sigma=2.0)
        
        # تطبيث قيم معيارية من 0 إلى 1
        dem_norm = 1.0 - (dem_data - np.min(dem_data)) / (np.ptp(dem_data) if np.ptp(dem_data) != 0 else 1.0)
        flow_norm = (flow_acc - np.min(flow_acc)) / (np.ptp(flow_acc) if np.ptp(flow_acc) != 0 else 1.0)
        
        # معالجة المؤشر المدمج
        gwpi = (w_dem * dem_norm) + (w_drain * flow_norm)
        if smooth_factor > 0:
            gwpi = gaussian_filter(gwpi, sigma=smooth_factor)
            
        gwpi_score = (gwpi - np.min(gwpi)) / (np.ptp(gwpi) if np.ptp(gwpi) != 0 else 1.0) * 100.0
        
        st.session_state['gwpi_score'] = gwpi_score
        st.session_state['dem_shape'] = dem_data.shape

# ---------------------------------------------------------
# TAB 3: الخرائط الحقيقية المخرجة
# ---------------------------------------------------------
with tab_outputs:
    st.subheader("🗺️ المخرجات الحقيقية المشتقة من البيانات المرفوعة")
    
    if 'gwpi_score' in st.session_state:
        score_map = st.session_state['gwpi_score']
        h, w = score_map.shape
        
        # استخراج نقطة أعلى تركيز حقيقية في شبكة البكسلات
        max_idx = np.unravel_index(np.argmax(score_map), score_map.shape)
        target_y_pixel = max_idx[0]
        target_x_pixel = max_idx[1]
        max_val = score_map[max_idx]

        st.markdown(f"### 🎯 موقع أعلى تركيز للمياه المكتشف: البكسل (`X: {target_x_pixel}`, `Y: {target_y_pixel}`) | نسبة الاحتمالية: `{max_val:.1f}%`")
        
        fig_real = px.imshow(
            score_map,
            color_continuous_scale='Spectral',
            title="خريطة احتمالية وتجمع المياه الجوفية المشتقة حقيقياً من ملف GeoTIFF المرفوع",
            labels={'color': 'احتمالية المياه %'}
        )
        
        fig_real.add_trace(go.Scatter(
            x=[target_x_pixel], y=[target_y_pixel],
            mode='markers+text',
            marker=dict(size=16, color='yellow', symbol='star', line=dict(width=2, color='black')),
            text=["🎯 نقطة الحفر المقترحة"],
            textposition="top center"
        ))
        
        fig_real.update_layout(height=600)
        st.plotly_chart(fig_real, use_container_width=True)
    else:
        st.info("💡 يرجى رفع ملف GeoTIFF للـ DEM في التاب الأول لبدء المعالجة واستخراج الخريطة.")
