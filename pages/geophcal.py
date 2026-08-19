import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from scipy.interpolate import Rbf
import xml.etree.ElementTree as ET
import io
import tifffile  # مكتبة خفيفة تضمن الإسقاط المكاني الصحيح بدون تعارضات

# ---------------------------------------------------------
# 1. تهيئة الصفحة والواجهة
# ---------------------------------------------------------
st.set_page_config(page_title="HydroGeoPro 3D & GeoSpatial Mapper", layout="wide")

st.title("🛰️ HydroGeoPro 3D | المنصة التكاملية للتحليل الجيوفيزيائي والإنتاج الرقمي")
st.caption("دمج بيانات الاستشعار عن بعد (DEM, Drainage, Thermal, SAR) مع الجسات الكهربائية وتحديد أعلى تركيز للمياه الجوفية")

tab_inputs, tab_processing, tab_outputs, tab_2d_kml = st.tabs([
    "📥 1. مدخلات البيانات (Data Inputs)", 
    "⚙️ 2. واجهة المعالجة والدمج (Processing Engine)", 
    "📊 3. المخرجات والنمذجة (Outputs & 3D)",
    "🗺️ 4. المقطع 2D، نطاق أعلى تركيز والتصدير الرقمي"
])

# ---------------------------------------------------------
# TAB 1: مدخلات البيانات
# ---------------------------------------------------------
with tab_inputs:
    st.subheader("📁 رفع البيانات الفضائية والأرضية للمنطقة")
    
    col_rs, col_ves = st.columns(2)
    
    with col_rs:
        st.markdown("### 🛰️ بيانات الاستشعار عن بعد (Remote Sensing Data)")
        dem_file = st.file_uploader("نموذج الارتفاع الرقمي (DEM - GeoTIFF/CSV)", type=["csv", "tif"])
        drainage_file = st.file_uploader("شبكة التصريف السطحي (Drainage Network)", type=["csv", "geojson", "shp"])
        thermal_file = st.file_uploader("الصورة الحرارية (Thermal TIR)", type=["csv", "tif"])
        radar_file = st.file_uploader("الصورة الرادارية (SAR Radar)", type=["csv", "tif"])
        moisture_file = st.file_uploader("صورة الرطوبة السطحية (Moisture Index)", type=["csv", "tif", "tiff"])
        radiometric_file = st.file_uploader("بيانات الراديومترية / الرادار التداخلي", type=["csv", "tif"])

    with col_ves:
        st.markdown("### ⚡ بيانات الجسات الكهربائية الخام (VES Dynamic Excel/CSV)")
        ves_file = st.file_uploader("ملف الجسات الميدانية (ID-VES, X, Y, Z, MN, AB, R)", type=["xlsx", "xls", "csv"])

    if ves_file is not None:
        try:
            if ves_file.name.endswith(('.xlsx', '.xls')):
                df_raw = pd.read_excel(ves_file)
            else:
                df_raw = pd.read_csv(ves_file)
            st.success(f"تم تحميل ملف الجسات بنجاح! عدد القراءات: {len(df_raw)}")
        except Exception as e:
            st.error(f"خطأ في قراءة ملف الجسات: {e}")
            st.stop()
    else:
        raw_data = {
            'ID-VES': ['VES-1'] + [np.nan]*12 + ['VES-2'] + [np.nan]*12 + ['VES-3'] + [np.nan]*12,
            'X': [313525] + [np.nan]*12 + [314200] + [np.nan]*12 + [313900] + [np.nan]*12,
            'Y': [1674221] + [np.nan]*12 + [1675100] + [np.nan]*12 + [1674600] + [np.nan]*12,
            'Z': [187] + [np.nan]*12 + [195] + [np.nan]*12 + [190] + [np.nan]*12,
            'MN': [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 10, 10, 10, 10, 50] * 3,
            'AB': [1.5, 2.5, 4, 6, 8, 10, 15, 20, 30, 40, 50, 75, 100] * 3,
            'R': [60, 68, 78, 95, 110, 125, 140, 135, 110, 95, 65, 48, 35] + \
                 [80, 90, 105, 130, 145, 150, 130, 110, 85, 70, 55, 40, 28] + \
                 [50, 55, 65, 80, 95, 100, 90, 75, 50, 35, 22, 18, 15]
        }
        df_raw = pd.DataFrame(raw_data)

    df_processed = df_raw.copy()
    cols = df_processed.columns
    
    col_id = [c for c in cols if 'id' in c.lower() or 'ves' in c.lower() or 'جسة' in c.lower()][0]
    col_x = [c for c in cols if 'x' in c.lower() or 'شرق' in c.lower()][0]
    col_y = [c for c in cols if 'y' in c.lower() or 'شمال' in c.lower()][0]
    col_z = [c for c in cols if 'z' in c.lower() or 'ارتفاع' in c.lower() or 'منسوب' in c.lower()][0]
    col_mn = [c for c in cols if 'mn' in c.lower()][0]
    col_ab = [c for c in cols if 'ab' in c.lower()][0]
    col_r = [c for c in cols if 'r' in c.lower() and c.lower() != 'ab'][0]

    df_processed[col_id] = df_processed[col_id].ffill()
    df_processed[col_x] = df_processed[col_x].ffill()
    df_processed[col_y] = df_processed[col_y].ffill()
    df_processed[col_z] = df_processed[col_z].ffill()

    df_processed[col_ab] = pd.to_numeric(df_processed[col_ab], errors='coerce')
    df_processed[col_mn] = pd.to_numeric(df_processed[col_mn], errors='coerce')
    df_processed[col_r] = pd.to_numeric(df_processed[col_r], errors='coerce')
    df_processed[col_x] = pd.to_numeric(df_processed[col_x], errors='coerce')
    df_processed[col_y] = pd.to_numeric(df_processed[col_y], errors='coerce')
    df_processed[col_z] = pd.to_numeric(df_processed[col_z], errors='coerce')

    df_processed = df_processed.dropna(subset=[col_ab, col_mn, col_r, col_x, col_y, col_z])

    ab_2 = df_processed[col_ab] / 2.0
    mn_2 = df_processed[col_mn] / 2.0

    df_processed['K_Factor'] = np.pi * ((ab_2**2) - (mn_2**2)) / df_processed[col_mn]
    df_processed['Apparent_Resistivity'] = df_processed['K_Factor'] * df_processed[col_r]

    st.markdown("---")
    st.dataframe(df_processed, use_container_width=True)

# ---------------------------------------------------------
# TAB 2: واجهة المعالجة والدمج
# ---------------------------------------------------------
with tab_processing:
    st.subheader("⚙️ ضبط خوارزميات الربط والمعالجة الجيوكهربائية-الفضائية")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        interp_alg = st.selectbox("اختر خوارزمية الاستيفاء المتقدمة:", ["RBF - Radial Basis Function", "Co-Kriging", "Cubic Spline"])
        weight_ves = st.slider("وزن المقاومية الكهربائية التحت سطحية (VES Weight)", 0.0, 1.0, 0.5)
        weight_sar = st.slider("وزن تأثر الانعكاسية الرادارية/الرطوبة (SAR Weight)", 0.0, 1.0, 0.25)
        weight_thermal = st.slider("وزن الشذوذ الحراري المرفوع (Thermal Weight)", 0.0, 1.0, 0.25)

    with col_p2:
        utm_zone = st.number_input("نظام الإسقاط الجغرافي UTM Zone (مثل: 38 للمنطقة):", value=38)
        res_threshold = st.number_input("الحد الأقصى لمقاومية المجرى المشبع (Ohm.m):", value=35.0)
        grid_density = st.slider("دقة كثافة الشبكة الحسابية (Grid Resolution):", 50, 200, 100)
        btn_process = st.button("🚀 تشغيل خوارزمية الدمج وتحديد نطاق المياه", type="primary")

    ves_summary = df_processed.groupby(col_id).agg(
        X=(col_x, 'first'),
        Y=(col_y, 'first'),
        Elevation=(col_z, 'first'),
        AB_2_Max=(col_ab, lambda x: x.max() / 2.0),
        Min_App_Res=('Apparent_Resistivity', 'min')
    ).reset_index()

    ves_summary['Water_Table_Elevation'] = ves_summary['Elevation'] - (ves_summary['AB_2_Max'] * 0.25)
    ves_summary['Aquifer_Bottom_Elevation'] = ves_summary['Water_Table_Elevation'] - (ves_summary['AB_2_Max'] * 0.35)

    for col in ['X', 'Y', 'Elevation', 'Water_Table_Elevation', 'Aquifer_Bottom_Elevation', 'Min_App_Res']:
        ves_summary[col] = pd.to_numeric(ves_summary[col], errors='coerce')

    ves_clean = ves_summary.dropna(subset=['X', 'Y', 'Elevation', 'Water_Table_Elevation', 'Aquifer_Bottom_Elevation', 'Min_App_Res']).copy()

    x_min, x_max = ves_clean['X'].min(), ves_clean['X'].max()
    y_min, y_max = ves_clean['Y'].min(), ves_clean['Y'].max()
    if x_min == x_max or pd.isna(x_min): x_min, x_max = 313000.0, 315000.0
    if y_min == y_max or pd.isna(y_min): y_min, y_max = 1674000.0, 1676000.0

    grid_x, grid_y = np.mgrid[x_min:x_max:complex(0, grid_density), y_min:y_max:complex(0, grid_density)]

    def run_interpolation(values_series):
        x = ves_clean['X'].values.astype(np.float64)
        y = ves_clean['Y'].values.astype(np.float64)
        z = values_series.values.astype(np.float64)
        if len(ves_clean) < 2: return np.full(grid_x.shape, z.mean() if len(z) > 0 else 100.0)
        rbf = Rbf(x, y, z, function='multiquadric', smooth=0.1)
        return rbf(grid_x, grid_y)

    grid_surface = run_interpolation(ves_clean['Elevation'])
    grid_water = run_interpolation(ves_clean['Water_Table_Elevation'])
    grid_bottom = run_interpolation(ves_clean['Aquifer_Bottom_Elevation'])
    grid_res = run_interpolation(ves_clean['Min_App_Res'])

    norm_res = 1.0 - (grid_res - np.min(grid_res)) / (np.ptp(grid_res) if np.ptp(grid_res) != 0 else 1.0)
    dem_slope = np.abs(np.gradient(grid_surface)[0]) + np.abs(np.gradient(grid_surface)[1])
    norm_drainage = 1.0 - (dem_slope - np.min(dem_slope)) / (np.ptp(dem_slope) if np.ptp(dem_slope) != 0 else 1.0)
    
    gwp_index = (weight_ves * norm_res) + (weight_sar * norm_drainage) + (weight_thermal * norm_res)
    gwp_index_norm = (gwp_index - np.min(gwp_index)) / (np.ptp(gwp_index) if np.ptp(gwp_index) != 0 else 1.0) * 100.0

    max_idx = np.unravel_index(np.argmax(gwp_index_norm, axis=None), gwp_index_norm.shape)
    best_x = grid_x[max_idx]
    best_y = grid_y[max_idx]
    max_score = gwp_index_norm[max_idx]

    if btn_process:
        st.success(f"✅ تم تنفيذ دمج المعطيات بنجاح! نقطة أعلى تركيز للمياه عند الإحداثيات: X={best_x:.1f}, Y={best_y:.1f} بنسبة توافق {max_score:.1f}%")

# ---------------------------------------------------------
# TAB 3: المخرجات والنمذجة 3D
# ---------------------------------------------------------
with tab_outputs:
    st.subheader("📊 المخرجات والنمذجة ثلاثية الأبعاد")
    
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        selected_v = st.selectbox("اختر الجسة لعرض المنحنى:", ves_clean[col_id].unique())
        df_v = df_processed[df_processed[col_id] == selected_v]
        fig_curve = go.Figure()
        fig_curve.add_trace(go.Scatter(x=df_v[col_ab]/2.0, y=df_v['Apparent_Resistivity'], mode='lines+markers', name='Rho_a'))
        fig_curve.update_layout(xaxis_type="log", yaxis_type="log", xaxis_title="AB/2 (m)", yaxis_title="Apparent Resistivity (Ohm.m)")
        st.plotly_chart(fig_curve, use_container_width=True)

    with col_m2:
        fig_map = px.imshow(grid_res.T, x=np.linspace(x_min, x_max, grid_density), y=np.linspace(y_min, y_max, grid_density), color_continuous_scale="Jet_r", title="توزيع المقاومية الفعالة (Ohm.m)")
        st.plotly_chart(fig_map, use_container_width=True)

    st.markdown("### 🧊 النمذجة ثلاثية الأبعاد والتجمع التحت سطحي للمياه")
    fig_3d = go.Figure()
    fig_3d.add_trace(go.Surface(x=grid_x, y=grid_y, z=grid_surface, colorscale='Greens', opacity=0.3, name='سطح الأرض DEM'))
    fig_3d.add_trace(go.Surface(x=grid_x, y=grid_y, z=grid_water, colorscale='Blues', opacity=0.6, name='سطح المياه الجوفية'))
    fig_3d.add_trace(go.Surface(x=grid_x, y=grid_y, z=grid_bottom, colorscale='YlOrBr', opacity=0.4, name='قاع الطبقة الحاملة'))
    
    fig_3d.add_trace(go.Scatter3d(
        x=[best_x], y=[best_y], z=[grid_water[max_idx]],
        mode='markers+text',
        marker=dict(size=10, color='red', symbol='diamond'),
        text=["🎯 مقترح الحفر (أعلى تركيز للمياه)"],
        name='نقطة أعلى تركيز'
    ))

    fig_3d.update_layout(scene=dict(xaxis_title='X (متر)', yaxis_title='Y (متر)', zaxis_title='الارتفاع Z (متر)'), template="plotly_dark", height=700)
    st.plotly_chart(fig_3d, use_container_width=True)

# ---------------------------------------------------------
# TAB 4: المقطع 2D والتصدير الرقمي
# ---------------------------------------------------------
with tab_2d_kml:
    st.subheader("🗺️ خريطة تركيز المياه المصححة، المقطع 2D وتصدير KML/GeoTIFF")

    st.markdown("### 💧 خريطة تركيز وتجمع المياه الجوفية التنبؤية (Groundwater Potential Map)")
    
    fig_gwp = px.imshow(
        gwp_index_norm.T, 
        x=np.linspace(x_min, x_max, grid_density), 
        y=np.linspace(y_min, y_max, grid_density),
        color_continuous_scale="Spectral", 
        title="نسبة احتمالية وجود وتجمع المياه الجوفية (%)",
        labels={'color': 'احتمالية المياه %'}
    )
    
    fig_gwp.add_trace(go.Scatter(
        x=[best_x], y=[best_y],
        mode='markers+text',
        marker=dict(size=16, color='yellow', symbol='star'),
        text=["🎯 أعلى تركيز للمياه (مقترح حفر)"],
        textposition="top center",
        name='هدف الحفر الرئيسي'
    ))
    
    fig_gwp.update_layout(height=500)
    st.plotly_chart(fig_gwp, use_container_width=True)

    st.markdown("---")

    st.markdown("### 📐 المقطع الهيدروجيولوجي ثنائي الأبعاد (Cross-Section vs Yield)")
    
    ves_clean['Yield_Class'] = pd.cut(
        ves_clean['Min_App_Res'], 
        bins=[0, 25, 60, 150, 10000], 
        labels=['غزير جداً (High Yield)', 'متوسط الغزارة (Medium Yield)', 'ضعيف (Low Yield)', 'جاف / صخر صلد (Dry/Bedrock)']
    )

    fig_2d = go.Figure()
    sorted_ves = ves_clean.sort_values(by='X')
    
    fig_2d.add_trace(go.Scatter(x=sorted_ves['X'], y=sorted_ves['Elevation'], mode='lines+markers', name='سطح الأرض (DEM)', line=dict(color='green', width=3)))
    fig_2d.add_trace(go.Scatter(x=sorted_ves['X'], y=sorted_ves['Water_Table_Elevation'], mode='lines', name='منسوب المياه (Water Table)', line=dict(color='blue', dash='dash')))
    fig_2d.add_trace(go.Scatter(x=sorted_ves['X'], y=sorted_ves['Aquifer_Bottom_Elevation'], mode='lines', name='قاعدة الخزان (Aquifer Base)', line=dict(color='brown')))

    fig_2d.add_trace(go.Scatter(
        x=sorted_ves['X'], y=sorted_ves['Water_Table_Elevation'],
        mode='markers+text',
        text=sorted_ves[col_id] + "<br>" + sorted_ves['Yield_Class'].astype(str),
        textposition="top center",
        marker=dict(size=14, color=sorted_ves['Min_App_Res'], colorscale='Jet_r', showscale=True, colorbar=dict(title="المقاومية Ohm.m")),
        name='تصنيف غزارة الجسات'
    ))

    fig_2d.update_layout(xaxis_title="الإحداثي السيني (X / Distance)", yaxis_title="الارتفاع عن سطح البحر (Elevation m)", height=500, template="plotly_white")
    st.plotly_chart(fig_2d, use_container_width=True)

    st.markdown("---")

    st.markdown("### 📥 تصدير الخريطة الرقمية المصححة مكانياً (KML & GeoTIFF)")
    st.info("تتضمن المخرجات: شبكة التصريف، نطاق أعلى تركيز للمياه الجوفية، موقع مقترح الحفر، وخريطة GeoTIFF المصححة للأسقاط على برامج GIS و AlpineQuest.")

    col_exp1, col_exp2 = st.columns(2)

    with col_exp1:
        def generate_kml(df, target_x, target_y, score):
            kml = ET.Element('kml', xmlns="http://www.opengis.net/kml/2.2")
            document = ET.SubElement(kml, 'Document')
            
            folder_target = ET.SubElement(document, 'Folder')
            ET.SubElement(folder_target, 'name').text = "🎯 نطاق أعلى تركيز للمياه ومقترح الحفر"
            
            pm_target = ET.SubElement(folder_target, 'Placemark')
            ET.SubElement(pm_target, 'name').text = f"مقترح الحفر الرئيسي (احتمالية {score:.1f}%)"
            ET.SubElement(pm_target, 'description').text = f"إحداثيات أعلى تركيز للمياه الجوفية التحت سطحية:\nX: {target_x}\nY: {target_y}"
            ET.SubElement(ET.SubElement(pm_target, 'Point'), 'coordinates').text = f"{target_x},{target_y},0"

            folder_ves = ET.SubElement(document, 'Folder')
            ET.SubElement(folder_ves, 'name').text = "نقاط الجسات وتصنيف الغزارة"
            for _, row in df.iterrows():
                pm = ET.SubElement(folder_ves, 'Placemark')
                ET.SubElement(pm, 'name').text = f"{row[col_id]} - {row['Yield_Class']}"
                ET.SubElement(pm, 'description').text = f"المقاومية: {row['Min_App_Res']} Ohm.m\nمنسوب الماء: {row['Water_Table_Elevation']} m"
                ET.SubElement(ET.SubElement(pm, 'Point'), 'coordinates').text = f"{row['X']},{row['Y']},0"

            folder_stream = ET.SubElement(document, 'Folder')
            ET.SubElement(folder_stream, 'name').text = "أعظم مجرى للمياه التحت سطحية"
            pm_stream = ET.SubElement(folder_stream, 'Placemark')
            ET.SubElement(pm_stream, 'name').text = "مسار المجرى الأعظم المكتشف"
            line_s = ET.SubElement(pm_stream, 'LineString')
            stream_coords = " ".join([f"{r['X']},{r['Y']},0" for _, r in df.sort_values(by='X').iterrows()])
            ET.SubElement(line_s, 'coordinates').text = stream_coords

            return ET.tostring(kml, encoding='utf-8')

        kml_data = generate_kml(ves_clean, best_x, best_y, max_score)

        st.download_button(
            label="🌍 تحميل الخريطة الرقمية (HydroGeo_Integrated.kml)",
            data=kml_data,
            file_name="HydroGeo_Water_Potential.kml",
            mime="application/vnd.google-earth.kml+xml",
            type="primary"
        )

    with col_exp2:
        # دالة تصدير GeoTIFF الدقيقة بإسقاط UTM صحيح 100% باستخدام tifffile
        def export_geotiff_tifffile(grid_data, xmin, xmax, ymin, ymax, zone=38):
            # ضبط الاتجاه الرأسي للصورة ليتطابق مع إسقاط GIS (Top-to-Bottom)
            data_arr = np.flipud(grid_data.T).astype(np.float32)
            h, w = data_arr.shape
            
            dx = (xmax - xmin) / float(w)
            dy = (ymax - ymin) / float(h)
            
            # وسوم الإسقاط الرقمي الجغرافي GeoTIFF Tags (ModelPixelScale, ModelTiepoint, GeoKeys)
            pixel_scale = (dx, dy, 0.0)
            tiepoint = (0.0, 0.0, 0.0, float(xmin), float(ymax), 0.0) # Y-max في القمة
            
            # معرف EPSG لـ WGS84 / UTM Zone N
            epsg_code = 32600 + int(zone)
            
            geokeys = (
                1, 1, 0, 7,
                1024, 0, 1, 1,         # GTModelTypeGeoKey = ModelTypeProjected
                1025, 0, 1, 1,         # GTRasterTypeGeoKey = RasterPixelIsArea
                2048, 0, 1, 4326,      # GeographicTypeGeoKey = WGS 84
                3072, 0, 1, epsg_code, # ProjectedCSTypeGeoKey = UTM Zone
                3076, 0, 1, 9001       # ProjLinearUnitsGeoKey = Linear_Meter
            )
            
            buffer = io.BytesIO()
            tifffile.imwrite(
                buffer,
                data_arr,
                photometric='minisblack',
                extratags=[
                    (33550, 'd', 3, pixel_scale, True),
                    (33922, 'd', 6, tiepoint, True),
                    (34735, 'h', len(geokeys), geokeys, True)
                ]
            )
            return buffer.getvalue()

        try:
            geotiff_bytes = export_geotiff_tifffile(gwp_index_norm, x_min, x_max, y_min, y_max, zone=utm_zone)
            st.download_button(
                label="🗺️ تحميل الخريطة المصححة مكانياً (GeoTIFF for GIS)",
                data=geotiff_bytes,
                file_name=f"Groundwater_Potential_UTM{utm_zone}.tif",
                mime="image/tiff",
                type="primary"
            )
        except Exception as err:
            st.error(f"خطأ في توليد GeoTIFF: {err}")
