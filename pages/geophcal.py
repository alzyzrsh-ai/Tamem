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
import math

# ---------------------------------------------------------
# دالة تحويل رياضية من UTM إلى WGS84 (Lat/Lon) بدون مكتبات خارجية
# ---------------------------------------------------------
def utm_to_wgs84(easting, northing, zone=38, northern_hemisphere=True):
    a = 6378137.0  # WGS84 semi-major axis
    f = 1 / 298.257223563  # WGS84 flattening
    b = a * (1 - f)
    e2 = (a**2 - b**2) / a**2
    e_prime2 = (a**2 - b**2) / b**2
    
    k0 = 0.9996
    x = easting - 500000.0
    y = northing if northern_hemisphere else northing - 10000000.0
    
    lon0 = (zone - 1) * 6 - 180 + 3
    lon0_rad = math.radians(lon0)
    
    M = y / k0
    mu = M / (a * (1 - e2/4 - 3*e2**2/64 - 5*e2**3/256))
    
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    
    phi1 = (mu + (3*e1/2 - 27*e1**3/32)*math.sin(2*mu) + 
            (21*e1**2/16 - 55*e1**4/32)*math.sin(4*mu) + 
            (151*e1**3/96)*math.sin(6*mu))
    
    N1 = a / math.sqrt(1 - e2 * math.sin(phi1)**2)
    T1 = math.tan(phi1)**2
    C1 = e_prime2 * math.cos(phi1)**2
    R1 = a * (1 - e2) / ((1 - e2 * math.sin(phi1)**2)**1.5)
    D = x / (N1 * k0)
    
    lat = phi1 - (N1 * math.tan(phi1) / R1) * (
        D**2/2 - (5 + 3*T1 + 10*C1 - 4*C1**2 - 9*e_prime2)*D**4/24 + 
        (61 + 90*T1 + 298*C1 + 45*T1**2 - 252*e_prime2 - 3*C1**2)*D**6/720
    )
    lon = lon0_rad + (
        D - (1 + 2*T1 + C1)*D**3/6 + 
        (5 - 2*C1 + 28*T1 - 3*C1**2 + 8*e_prime2 + 24*T1**2)*D**5/120
    ) / math.cos(phi1)
    
    return math.degrees(lon), math.degrees(lat)

# ---------------------------------------------------------
# 1. إعدادات الصفحة والتهيئة
# ---------------------------------------------------------
st.set_page_config(page_title="HydroGeo-AI Extrapolator Pro", layout="wide")

st.title("🌋 HydroGeo-AI | محرك النمذجة والتنبؤ الجيوفيزيائي التحت سطحي")
st.caption("ربط المسوحات الكهربائية الميدانية بالمؤشرات الفضائية لتعميم وبناء نموذج الطبقات والمياه الجوفية لباقي المنطقة")

tab_inputs, tab_model, tab_3d_strat, tab_export = st.tabs([
    "📥 1. مدخلات البيانات والتطابق المكاني", 
    "🧠 2. محرك التنبؤ والاستقراء (Spatial Machine Regression)", 
    "🧊 3. النمذجة ثلاثية الأبعاد والمقاطع الطباقية (3D Stratigraphy)",
    "🗺️ 4. الخرائط التنبؤية المتقدمة والتصدير الميداني"
])

# ---------------------------------------------------------
# TAB 1: مدخلات البيانات وتوفير البيانات الافتراضية الذكية
# ---------------------------------------------------------
with tab_inputs:
    col_rs, col_ves = st.columns(2)
    
    with col_rs:
        st.markdown("### 🛰️ بيانات الاستشعار عن بعد (Rasters)")
        dem_file = st.file_uploader("نموذج الارتفاع الرقمي (DEM - GeoTIFF)", type=["tif", "tiff"], key="dem_input")

    with col_ves:
        st.markdown("### ⚡ بيانات الجسات الجيوكهربائية (VES Soundings)")
        ves_file = st.file_uploader("جدول الجسات (Excel/CSV)", type=["xlsx", "xls", "csv"], key="ves_input")

    if dem_file is not None:
        try:
            dem_data = tifffile.imread(io.BytesIO(dem_file.read()))
            if dem_data.ndim > 2: dem_data = dem_data[:, :, 0]
            st.success(f"✅ تم تحميل DEM بمقاس {dem_data.shape[1]}x{dem_data.shape[0]} بكسل")
        except Exception as e:
            st.error(f"خطأ في قراءة ملف GeoTIFF: {e}")
            dem_data = None
    else:
        x_grid = np.linspace(313000, 318000, 100)
        y_grid = np.linspace(1673000, 1678000, 100)
        X, Y = np.meshgrid(x_grid, y_grid)
        dem_data = 2200 - 0.05 * (X - 313000) - 0.08 * (Y - 1673000) - 120 * np.exp(-((X - 315500)**2 + (Y - 1675500)**2) / 2e6)
        st.info("💡 يتم استخدام نموذج حوض هيدرولوجي كبيانات افتراضية للتحليل لعدم رفع ملف DEM.")

    st.session_state['dem_raster'] = dem_data

    if ves_file is not None:
        try:
            if ves_file.name.endswith(('.xlsx', '.xls')):
                df_raw = pd.read_excel(ves_file)
            else:
                df_raw = pd.read_csv(ves_file)
            st.session_state['df_raw'] = df_raw
            st.success("✅ تم قراءة جدول الجسات بنجاح.")
        except Exception as e:
            st.error(f"خطأ في قراءة ملف الجسات: {e}")
            df_raw = None
    else:
        df_raw = pd.DataFrame({
            'ID-VES': [f'VES-{i+1}' for i in range(8)],
            'X': [313500, 314200, 315000, 315800, 316500, 314800, 315500, 316200],
            'Y': [1674000, 1674500, 1675000, 1675500, 1676000, 1676500, 1677000, 1677500],
            'Z': [2150, 2120, 2080, 2040, 2010, 2090, 2050, 2020],
            'Resistivity_Ohm': [120.0, 85.0, 35.0, 18.0, 22.0, 45.0, 25.0, 15.0],
            'Aquifer_Depth_m': [45.0, 38.0, 22.0, 14.0, 16.0, 28.0, 18.0, 12.0],
            'Aquifer_Thickness_m': [15.0, 22.0, 40.0, 55.0, 50.0, 30.0, 45.0, 60.0]
        })
        st.session_state['df_raw'] = df_raw

    st.dataframe(st.session_state['df_raw'], use_container_width=True)

# ---------------------------------------------------------
# TAB 2: محرك التنبؤ والاستقراء المكاني
# ---------------------------------------------------------
with tab_model:
    st.subheader("🧠 استقراء سلوك الطبقات العميقة بناءً على مؤشرات السطح")
    col_m1, col_m2 = st.columns(2)
    
    df_v = st.session_state.get('df_raw', pd.DataFrame()).copy()
    cols = df_v.columns
    col_x = [c for c in cols if any(k in str(c).lower() for k in ['x', 'شرق', 'east'])][0] if any(any(k in str(c).lower() for k in ['x', 'شرق', 'east']) for c in cols) else 'X'
    col_y = [c for c in cols if any(k in str(c).lower() for k in ['y', 'شمال', 'north'])][0] if any(any(k in str(c).lower() for k in ['y', 'شمال', 'north']) for c in cols) else 'Y'
    col_z = [c for c in cols if any(k in str(c).lower() for k in ['z', 'ارتفاع', 'elev'])][0] if any(any(k in str(c).lower() for k in ['z', 'ارتفاع', 'elev']) for c in cols) else 'Z'

    df_v[col_x] = df_v[col_x].ffill()
    df_v[col_y] = df_v[col_y].ffill()

    for c in [col_x, col_y, col_z, 'Resistivity_Ohm', 'Aquifer_Depth_m', 'Aquifer_Thickness_m']:
        if c in df_v.columns:
            df_v[c] = pd.to_numeric(df_v[c], errors='coerce')

    ves_clean = df_v.dropna(subset=[col_x, col_y]).copy()

    if 'Resistivity_Ohm' not in ves_clean.columns: ves_clean['Resistivity_Ohm'] = 35.0
    if 'Aquifer_Depth_m' not in ves_clean.columns: ves_clean['Aquifer_Depth_m'] = 25.0
    if 'Aquifer_Thickness_m' not in ves_clean.columns: ves_clean['Aquifer_Thickness_m'] = 40.0
    if col_z not in ves_clean.columns: ves_clean[col_z] = 2000.0

    if ves_clean.empty:
        st.error("⚠️ لم يتم العثور على أرقام إحداثيات صالحة.")
        st.stop()

    with col_m1:
        st.markdown("#### 1. استخرج المتغيرات الفضائية عند موقع الجسات")
        dy, dx = np.gradient(dem_data)
        slope = np.sqrt(dx**2 + dy**2)
        flow_accumulation = gaussian_filter(1.0 / (slope + 0.005), sigma=3.0)
        
        x_min, x_max = float(ves_clean[col_x].min()) - 1000, float(ves_clean[col_x].max()) + 1000
        y_min, y_max = float(ves_clean[col_y].min()) - 1000, float(ves_clean[col_y].max()) + 1000
        st.success(f"✅ تم تنقية البيانات! الجسات الصالحة: {len(ves_clean)}")

    with col_m2:
        st.markdown("#### 2. خوارزميات الاستقراء الهيدروجيوفيزيائي")
        corr_weight = st.slider("معامل تأثير شبكة التصريف المائي:", 0.1, 1.0, 0.65)

    ny, nx = dem_data.shape
    gx = np.linspace(x_min, x_max, nx)
    gy = np.linspace(y_min, y_max, ny)
    grid_X, grid_Y = np.meshgrid(gx, gy)

    rbf_res = Rbf(ves_clean[col_x], ves_clean[col_y], ves_clean['Resistivity_Ohm'], function='multiquadric', smooth=0.1)
    pred_res_base = rbf_res(grid_X, grid_Y)
    
    flow_norm = (flow_accumulation - np.min(flow_accumulation)) / (np.ptp(flow_accumulation) + 1e-6)
    predicted_resistivity = pred_res_base * (1.0 - (corr_weight * 0.5 * flow_norm))

    rbf_depth = Rbf(ves_clean[col_x], ves_clean[col_y], ves_clean['Aquifer_Depth_m'], function='multiquadric', smooth=0.1)
    predicted_depth = rbf_depth(grid_X, grid_Y)
    
    rbf_thick = Rbf(ves_clean[col_x], ves_clean[col_y], ves_clean['Aquifer_Thickness_m'], function='multiquadric', smooth=0.1)
    predicted_thickness = rbf_thick(grid_X, grid_Y) * (1.0 + (corr_weight * 0.4 * flow_norm))

    surface_z = dem_data
    water_table_z = surface_z - predicted_depth
    aquifer_bottom_z = water_table_z - predicted_thickness

    st.session_state['predicted_res'] = predicted_resistivity
    st.session_state['surface_z'] = surface_z
    st.session_state['water_table_z'] = water_table_z
    st.session_state['aquifer_bottom_z'] = aquifer_bottom_z
    st.session_state['grid_X'] = grid_X
    st.session_state['grid_Y'] = grid_Y
    st.session_state['gx'] = gx
    st.session_state['gy'] = gy
    st.session_state['ves_clean'] = ves_clean
    st.session_state['col_x'] = col_x
    st.session_state['col_y'] = col_y
    st.session_state['col_z'] = col_z

# ---------------------------------------------------------
# TAB 3: النمذجة ثلاثية الأبعاد
# ---------------------------------------------------------
with tab_3d_strat:
    st.subheader("🧊 النماذج ثلاثية الأبعاد للطبقات والمياه")
    ves_clean = st.session_state.get('ves_clean', pd.DataFrame())
    col_x = st.session_state.get('col_x', 'X')
    col_y = st.session_state.get('col_y', 'Y')
    col_z = st.session_state.get('col_z', 'Z')

    if 'surface_z' in st.session_state:
        fig_3d = go.Figure()
        fig_3d.add_trace(go.Surface(x=st.session_state['grid_X'], y=st.session_state['grid_Y'], z=st.session_state['surface_z'], colorscale='Greens', opacity=0.35, showscale=False))
        fig_3d.add_trace(go.Surface(x=st.session_state['grid_X'], y=st.session_state['grid_Y'], z=st.session_state['water_table_z'], surfacecolor=st.session_state['predicted_res'], colorscale='Jet_r', opacity=0.75))
        fig_3d.add_trace(go.Scatter3d(x=ves_clean[col_x], y=ves_clean[col_y], z=ves_clean[col_z], mode='markers', marker=dict(size=8, color='red')))
        fig_3d.update_layout(scene=dict(aspectratio=dict(x=1, y=1, z=0.4)), template="plotly_dark", height=600)
        st.plotly_chart(fig_3d, use_container_width=True)

# ---------------------------------------------------------
# TAB 4: الخرائط التنبؤية المتقدمة والتصدير الميداني الدقيق
# ---------------------------------------------------------
with tab_export:
    st.subheader("🗺️ إعدادات الإسقاط وتصدير الخريطة التنبؤية لـ Google Earth")

    if 'predicted_res' in st.session_state:
        col_proj1, col_proj2 = st.columns(2)
        
        with col_proj1:
            st.markdown("### 🌐 تحديد نظام الإحداثيات الميداني")
            utm_zone = st.number_input("رقم نطاق UTM (مثلاً 38 لليمن ورأس المعزاب/الجوف/صنعاء):", min_value=1, max_value=60, value=38)
            is_northern = st.checkbox("النصف الشمالي من الكرة الأرضية (Northern Hemisphere)", value=True)

        with col_proj2:
            st.markdown("### 🛠️ معايير تصدير KML الميداني")
            grid_resolution = st.slider("دقة الشبكة المصدّرة (دقة أعلى = ملف أكبر):", 1, 6, 3)

        def generate_accurate_kml(grid_X, grid_Y, pred_data, ves_df, cx, cy, zone, is_north, step=3):
            kml = ET.Element('kml', xmlns="http://www.opengis.net/kml/2.2")
            doc = ET.SubElement(kml, 'Document')
            ET.SubElement(doc, 'name').text = "HydroGeo Predictive Map (Georeferenced)"

            min_v, max_v = np.nanmin(pred_data), np.nanmax(pred_data)
            rows, cols = pred_data.shape
            
            folder_polys = ET.SubElement(doc, 'Folder')
            ET.SubElement(folder_polys, 'name').text = "تغطية خريطة المقاومية التنبؤية"

            for i in range(0, rows - step, step):
                for j in range(0, cols - step, step):
                    val = pred_data[i, j]
                    if np.isnan(val): continue
                    
                    norm_val = (val - min_v) / (max_v - min_v + 1e-6)
                    r = int(255 * (1.0 - norm_val))
                    b = int(255 * norm_val)
                    g = int(255 * (1.0 - abs(norm_val - 0.5) * 2))
                    
                    color_hex = f"aa{b:02x}{g:02x}{r:02x}"
                    
                    style = ET.SubElement(doc, 'Style', id=f"s_{i}_{j}")
                    polystyle = ET.SubElement(style, 'PolyStyle')
                    ET.SubElement(polystyle, 'color').text = color_hex
                    ET.SubElement(polystyle, 'outline').text = "0"

                    pm = ET.SubElement(folder_polys, 'Placemark')
                    ET.SubElement(pm, 'styleUrl').text = f"#s_{i}_{j}"
                    
                    x1, x2 = grid_X[i, j], grid_X[min(i+step, rows-1), min(j+step, cols-1)]
                    y1, y2 = grid_Y[i, j], grid_Y[min(i+step, rows-1), min(j+step, cols-1)]
                    
                    # التحويل المباشر دون الاعتماد على مكتبات إضافية
                    lon1, lat1 = utm_to_wgs84(x1, y1, zone=zone, northern_hemisphere=is_north)
                    lon2, lat2 = utm_to_wgs84(x2, y1, zone=zone, northern_hemisphere=is_north)
                    lon3, lat3 = utm_to_wgs84(x2, y2, zone=zone, northern_hemisphere=is_north)
                    lon4, lat4 = utm_to_wgs84(x1, y2, zone=zone, northern_hemisphere=is_north)

                    poly = ET.SubElement(pm, 'Polygon')
                    boundary = ET.SubElement(poly, 'outerBoundaryIs')
                    ring = ET.SubElement(boundary, 'LinearRing')
                    ET.SubElement(ring, 'coordinates').text = (
                        f"{lon1},{lat1},0 {lon2},{lat2},0 {lon3},{lat3},0 {lon4},{lat4},0 {lon1},{lat1},0"
                    )

            folder_pts = ET.SubElement(doc, 'Folder')
            ET.SubElement(folder_pts, 'name').text = "مواقع الجسات الميدانية"
            for idx, r in ves_df.iterrows():
                lon_p, lat_p = utm_to_wgs84(r[cx], r[cy], zone=zone, northern_hemisphere=is_north)
                pm_pt = ET.SubElement(folder_pts, 'Placemark')
                ET.SubElement(pm_pt, 'name').text = f"VES-{idx+1}"
                ET.SubElement(ET.SubElement(pm_pt, 'Point'), 'coordinates').text = f"{lon_p},{lat_p},0"

            return ET.tostring(kml, encoding='utf-8')

        st.markdown("---")
        
        correct_kml_data = generate_accurate_kml(
            st.session_state['grid_X'],
            st.session_state['grid_Y'],
            st.session_state['predicted_res'],
            st.session_state['ves_clean'],
            st.session_state['col_x'],
            st.session_state['col_y'],
            utm_zone,
            is_northern,
            step=grid_resolution
        )

        st.download_button(
            label="🌍 تحميل الخريطة التنبؤية الموجهة جغرافياً (Standalone WGS84 KML) لـ Google Earth / AlpineQuest",
            data=correct_kml_data,
            file_name="HydroGeo_RealWorld_Map.kml",
            mime="application/vnd.google-earth.kml+xml",
            type="primary"
        )
