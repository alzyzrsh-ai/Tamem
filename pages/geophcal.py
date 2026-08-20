import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf
from scipy.ndimage import gaussian_filter
import xml.etree.ElementTree as ET
import io
import tifffile
import math

# ---------------------------------------------------------
# دالة التحويل المباشر من UTM إلى WGS84 (Lat/Lon)
# ---------------------------------------------------------
def utm_to_wgs84(easting, northing, zone=38, northern_hemisphere=True):
    a = 6378137.0
    f = 1 / 298.257223563
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
# تهيئة واجهة Streamlit
# ---------------------------------------------------------
st.set_page_config(page_title="HydroGeo Real-World Modeler", layout="wide")
st.title("🌋 HydroGeo-AI | النموذج الاستقرائي الواقعي والمنتظم")

tab_inputs, tab_model, tab_export = st.tabs([
    "📥 1. مدخلات البيانات والجسات", 
    "🧠 2. المعالجة والاستقراء الميداني", 
    "🗺️ 3. تصدير KML المباشر لـ Google Earth"
])

# ---------------------------------------------------------
# Tab 1: مدخلات البيانات
# ---------------------------------------------------------
with tab_inputs:
    col_ves, col_dem = st.columns(2)
    with col_ves:
        ves_file = st.file_uploader("رفع جدول الجسات (CSV/Excel)", type=["csv", "xlsx", "xls"])
    with col_dem:
        dem_file = st.file_uploader("رفع DEM (GeoTIFF اختياري)", type=["tif", "tiff"])

    if ves_file is not None:
        try:
            df_raw = pd.read_excel(ves_file) if ves_file.name.endswith(('.xlsx', '.xls')) else pd.read_csv(ves_file)
            st.success("✅ تم قراءة جدول البيانات بنجاح.")
        except Exception as e:
            st.error(f"خطأ في قراءة ملف الجسات: {e}")
            df_raw = None
    else:
        df_raw = pd.DataFrame({
            'ID-VES': ['VES-1', 'VES-2', 'VES-3'],
            'X': [313500, 315200, 317100],
            'Y': [1674000, 1675500, 1677200],
            'Z': [2150, 2080, 2010],
            'Resistivity_Ohm': [120.0, 45.0, 15.0],
            'Aquifer_Depth_m': [45.0, 25.0, 12.0],
            'Aquifer_Thickness_m': [15.0, 35.0, 60.0]
        })
        st.info("💡 يتم عرض بيانات افتراضية ممثلة لقطاع متدرج منتظم لعدم رفع ملف.")

    st.session_state['df_raw'] = df_raw
    st.dataframe(df_raw, use_container_width=True)

# ---------------------------------------------------------
# Tab 2: خوارزمية الاستقراء والوقاية من KeyError
# ---------------------------------------------------------
with tab_model:
    st.subheader("⚙️ خوارزمية التنعيم والاستقراء الميداني الموزون")
    
    df_v = st.session_state['df_raw'].copy()
    
    # خوارزمية التعرف الذكي على أسماء الأعمدة لتفادي خطأ KeyError
    cols_map = {str(c).strip().lower(): c for c in df_v.columns}

    def find_column(keywords, default_name):
        for kw in keywords:
            for c_lower, c_original in cols_map.items():
                if kw in c_lower:
                    return c_original
        return default_name

    col_x = find_column(['x', 'east', 'شرق', 'إحداثي x'], 'X')
    col_y = find_column(['y', 'north', 'شمال', 'إحداثي y'], 'Y')
    col_z = find_column(['z', 'elev', 'ارتفاع', 'منسوب'], 'Z')
    col_res = find_column(['res', 'ohm', 'مقاوم', 'resistivity', 'rho'], 'Resistivity_Ohm')

    # التأكد من وجود الأعمدة المعتمدة
    if col_x not in df_v.columns: df_v[col_x] = 0.0
    if col_y not in df_v.columns: df_v[col_y] = 0.0
    if col_z not in df_v.columns: df_v[col_z] = 2000.0
    if col_res not in df_v.columns: df_v[col_res] = 30.0

    # تحويل القيم لبيانات رقمية وحذف الصفوف التالفة
    for c in [col_x, col_y, col_z, col_res]:
        df_v[c] = pd.to_numeric(df_v[c], errors='coerce')
    
    ves_clean = df_v.dropna(subset=[col_x, col_y, col_res]).copy()

    if len(ves_clean) < 3:
        st.error("⚠️ يتطلب الاستقراء وجود 3 نقاط/جسات صالحة تحتوي على إحداثيات ومقاومية على الأقل.")
        st.stop()

    # نطاق شبكة العينات
    x_min, x_max = float(ves_clean[col_x].min()) - 1500, float(ves_clean[col_x].max()) + 1500
    y_min, y_max = float(ves_clean[col_y].min()) - 1500, float(ves_clean[col_y].max()) + 1500
    
    nx, ny = 100, 100
    gx = np.linspace(x_min, x_max, nx)
    gy = np.linspace(y_min, y_max, ny)
    grid_X, grid_Y = np.meshgrid(gx, gy)

    smooth_factor = st.slider("معامل تنعيم التدرج اللوني (Smooth Factor):", 0.1, 10.0, 2.5)

    try:
        rbf_model = Rbf(
            ves_clean[col_x], 
            ves_clean[col_y], 
            ves_clean[col_res], 
            function='thin_plate', 
            smooth=smooth_factor
        )
        predicted_res = rbf_model(grid_X, grid_Y)

        st.session_state['grid_X'] = grid_X
        st.session_state['grid_Y'] = grid_Y
        st.session_state['predicted_res'] = predicted_res
        st.session_state['ves_clean'] = ves_clean
        st.session_state['col_x'] = col_x
        st.session_state['col_y'] = col_y

        st.success(f"✅ تم تنفيذ الاستقراء لعدد {len(ves_clean)} جسة ميدانية دون أي أخطاء.")
    except Exception as e:
        st.error(f"حدث خطأ أثناء تنفيذ RBF: {e}")

# ---------------------------------------------------------
# Tab 3: التصدير لـ KML
# ---------------------------------------------------------
with tab_export:
    st.subheader("🗺️ تصدير خريطة KML الدقيقة والمطابقة ميدانياً")
    
    utm_zone = st.number_input("رقم نطاق UTM (مثلاً 38 لليمن ونجران والجوف وصنعاء):", min_value=1, max_value=60, value=38)
    is_north = st.checkbox("النصف الشمالي (Northern Hemisphere)", value=True)
    grid_step = st.slider("دقة تصدير المربعات لـ KML:", 1, 5, 2)

    def export_realistic_kml(grid_X, grid_Y, pred_data, ves_df, cx, cy, zone, is_north_hemi, step=2):
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
                r = int(255 * norm_val)
                g = int(255 * (1.0 - abs(norm_val - 0.5) * 2))
                b = int(255 * (1.0 - norm_val))
                
                color_hex = f"aa{b:02x}{g:02x}{r:02x}"
                
                style = ET.SubElement(doc, 'Style', id=f"s_{i}_{j}")
                polystyle = ET.SubElement(style, 'PolyStyle')
                ET.SubElement(polystyle, 'color').text = color_hex
                ET.SubElement(polystyle, 'outline').text = "0"

                pm = ET.SubElement(folder_polys, 'Placemark')
                ET.SubElement(pm, 'styleUrl').text = f"#s_{i}_{j}"
                
                x1, x2 = grid_X[i, j], grid_X[min(i+step, rows-1), min(j+step, cols-1)]
                y1, y2 = grid_Y[i, j], grid_Y[min(i+step, rows-1), min(j+step, cols-1)]
                
                lon1, lat1 = utm_to_wgs84(x1, y1, zone=zone, northern_hemisphere=is_north_hemi)
                lon2, lat2 = utm_to_wgs84(x2, y1, zone=zone, northern_hemisphere=is_north_hemi)
                lon3, lat3 = utm_to_wgs84(x2, y2, zone=zone, northern_hemisphere=is_north_hemi)
                lon4, lat4 = utm_to_wgs84(x1, y2, zone=zone, northern_hemisphere=is_north_hemi)

                poly = ET.SubElement(pm, 'Polygon')
                boundary = ET.SubElement(poly, 'outerBoundaryIs')
                ring = ET.SubElement(boundary, 'LinearRing')
                ET.SubElement(ring, 'coordinates').text = (
                    f"{lon1},{lat1},0 {lon2},{lat2},0 {lon3},{lat3},0 {lon4},{lat4},0 {lon1},{lat1},0"
                )

        folder_pts = ET.SubElement(doc, 'Folder')
        ET.SubElement(folder_pts, 'name').text = "مواقع الجسات الميدانية"
        for idx, r_row in ves_df.iterrows():
            lon_p, lat_p = utm_to_wgs84(r_row[cx], r_row[cy], zone=zone, northern_hemisphere=is_north_hemi)
            pm_pt = ET.SubElement(folder_pts, 'Placemark')
            ves_name = r_row.get('ID-VES', f"VES-{idx+1}")
            ET.SubElement(pm_pt, 'name').text = str(ves_name)
            ET.SubElement(ET.SubElement(pm_pt, 'Point'), 'coordinates').text = f"{lon_p},{lat_p},0"

        return ET.tostring(kml, encoding='utf-8')

    if 'predicted_res' in st.session_state:
        kml_out = export_realistic_kml(
            st.session_state['grid_X'],
            st.session_state['grid_Y'],
            st.session_state['predicted_res'],
            st.session_state['ves_clean'],
            st.session_state['col_x'],
            st.session_state['col_y'],
            utm_zone,
            is_north,
            step=grid_step
        )

        st.download_button(
            label="🌍 تحميل ملف KML النمط الواقعي المباشر لـ Google Earth",
            data=kml_out,
            file_name="HydroGeo_Realistic_Model.kml",
            mime="application/vnd.google-earth.kml+xml",
            type="primary"
        )
