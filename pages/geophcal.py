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
    "🗺️ 4. الخرائط التنبؤية المتقدمة والتصدير"
])

# ---------------------------------------------------------
# TAB 1: مدخلات البيانات وتوفير البيانات الافتراضية الذكية
# ---------------------------------------------------------
with tab_inputs:
    col_rs, col_ves = st.columns(2)
    
    with col_rs:
        st.markdown("### 🛰️ بيانات الاستشعار عن بعد (Rasters)")
        dem_file = st.file_uploader("نموذج الارتفاع الرقمي (DEM - GeoTIFF)", type=["tif", "tiff"], key="dem_input")
        thermal_file = st.file_uploader("الصورة الحرارية / LST (GeoTIFF)", type=["tif", "tiff"], key="thermal_input")
        radar_file = st.file_uploader("الصورة الرادارية / SAR (GeoTIFF)", type=["tif", "tiff"], key="radar_input")

    with col_ves:
        st.markdown("### ⚡ بيانات الجسات الجيوكهربائية (VES Soundings)")
        ves_file = st.file_uploader("جدول الجسات (Excel/CSV)", type=["xlsx", "xls", "csv"], key="ves_input")

    # معالجة قراءة GeoTIFF أو إنشاء مصفوفة طوبوغرافية حقيقية افتراضية في حالة عدم الرفع
    if dem_file is not None:
        try:
            dem_data = tifffile.imread(io.BytesIO(dem_file.read()))
            if dem_data.ndim > 2: dem_data = dem_data[:, :, 0]
            st.success(f"✅ تم تحميل DEM بمقاس {dem_data.shape[1]}x{dem_data.shape[0]} بكسل")
        except Exception as e:
            st.error(f"خطأ في قراءة ملف GeoTIFF: {e}")
            dem_data = None
    else:
        # إنشاء مصفوفة حوض هيدرولوجي واقعي في حالة عدم رفع ملف DEM
        x_grid = np.linspace(313000, 318000, 100)
        y_grid = np.linspace(1673000, 1678000, 100)
        X, Y = np.meshgrid(x_grid, y_grid)
        dem_data = 2200 - 0.05 * (X - 313000) - 0.08 * (Y - 1673000) - 120 * np.exp(-((X - 315500)**2 + (Y - 1675500)**2) / 2e6)
        st.info("💡 يتم استخدام نموذج حوض هيدرولوجي كبيانات افتراضية للتحليل لعدم رفع ملف DEM.")

    st.session_state['dem_raster'] = dem_data

    # معالجة قراءة الجسات الجيوكهربائية
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
        # نقاط جسات ميدانية نموذجية في حالة عدم الرفع
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
# TAB 2: محرك التنبؤ والاستقراء المكاني (معالجة أخطاء None)
# ---------------------------------------------------------
with tab_model:
    st.subheader("🧠 استقراء سلوك الطبقات العميقة بناءً على مؤشرات السطح")
    
    col_m1, col_m2 = st.columns(2)
    
    # 1. تنقية وتجهيز الجداول رقمياً بأمان تام
    df_v = st.session_state.get('df_raw', pd.DataFrame()).copy()
    
    # محاذاة أسماء الأعمدة الأساسية
    cols = df_v.columns
    col_x = [c for c in cols if any(k in str(c).lower() for k in ['x', 'شرق', 'east'])][0] if any(any(k in str(c).lower() for k in ['x', 'شرق', 'east']) for c in cols) else 'X'
    col_y = [c for c in cols if any(k in str(c).lower() for k in ['y', 'شمال', 'north'])][0] if any(any(k in str(c).lower() for k in ['y', 'شمال', 'north']) for c in cols) else 'Y'
    col_z = [c for c in cols if any(k in str(c).lower() for k in ['z', 'ارتفاع', 'elev'])][0] if any(any(k in str(c).lower() for k in ['z', 'ارتفاع', 'elev']) for c in cols) else 'Z'

    # ملء اسم الجسة وقرائن العمود
    df_v[col_x] = df_v[col_x].ffill()
    df_v[col_y] = df_v[col_y].ffill()

    # تحويل كافة القيم الحسابية إلى أرقام وإلغاء النصوص والأجزاء الفارغة None
    for c in [col_x, col_y, col_z, 'Resistivity_Ohm', 'Aquifer_Depth_m', 'Aquifer_Thickness_m']:
        if c in df_v.columns:
            df_v[c] = pd.to_numeric(df_v[c], errors='coerce')

    # حذف الأسطر التي تحتوي على None أو NaN في الإحداثيات
    ves_clean = df_v.dropna(subset=[col_x, col_y]).copy()

    # إنشاء قيم افتراضية حقلية إذا غابت بعض الأعمدة التنبؤية من الجدول المرفوع
    if 'Resistivity_Ohm' not in ves_clean.columns: ves_clean['Resistivity_Ohm'] = 35.0
    if 'Aquifer_Depth_m' not in ves_clean.columns: ves_clean['Aquifer_Depth_m'] = 25.0
    if 'Aquifer_Thickness_m' not in ves_clean.columns: ves_clean['Aquifer_Thickness_m'] = 40.0
    if col_z not in ves_clean.columns: ves_clean[col_z] = 2000.0

    if ves_clean.empty:
        st.error("⚠️ لم يتم العثور على أرقام إحداثيات صالحة (X, Y) في الملف. يرجى رفع ملف يحتوي على أرقام الإحداثيات.")
        st.stop()

    with col_m1:
        st.markdown("#### 1. استخرج المتغيرات الفضائية عند موقع الجسات")
        dy, dx = np.gradient(dem_data)
        slope = np.sqrt(dx**2 + dy**2)
        flow_accumulation = gaussian_filter(1.0 / (slope + 0.005), sigma=3.0)
        
        # حساب الحدود المكانية المباشرة بأمان بدون خطأ None
        x_min, x_max = float(ves_clean[col_x].min()) - 1000, float(ves_clean[col_x].max()) + 1000
        y_min, y_max = float(ves_clean[col_y].min()) - 1000, float(ves_clean[col_y].max()) + 1000
        
        st.success(f"✅ تم تنقية البيانات بنجاح! عدد نقاط الجسات النظيفة: {len(ves_clean)}")

    with col_m2:
        st.markdown("#### 2. خوارزميات الاستقراء الهيدروجيوفيزيائي")
        model_type = st.selectbox("اختر نموذج المعايرة الميدانية:", [
            "RBF - Radial Basis Function Integration",
            "Multi-Parametric Regression (DEM + Flow -> Resistivity)",
            "Inverse Distance & Slope Hydro-Weighting"
        ])
        corr_weight = st.slider("معامل تأثير شبكة التصريف المائي في النمذجة العمقية:", 0.1, 1.0, 0.65)

    # بناء الشبكة التنبؤية لعموم الحوض
    ny, nx = dem_data.shape
    gx = np.linspace(x_min, x_max, nx)
    gy = np.linspace(y_min, y_max, ny)
    grid_X, grid_Y = np.meshgrid(gx, gy)

    # التنبؤ الهيدروجيوفيزيائي للطبقات العميقة
    rbf_res = Rbf(ves_clean[col_x], ves_clean[col_y], ves_clean['Resistivity_Ohm'], function='multiquadric', smooth=0.1)
    pred_res_base = rbf_res(grid_X, grid_Y)
    
    flow_norm = (flow_accumulation - np.min(flow_accumulation)) / (np.ptp(flow_accumulation) + 1e-6)
    predicted_resistivity = pred_res_base * (1.0 - (corr_weight * 0.5 * flow_norm))

    rbf_depth = Rbf(ves_clean[col_x], ves_clean[col_y], ves_clean['Aquifer_Depth_m'], function='multiquadric', smooth=0.1)
    predicted_depth = rbf_depth(grid_X, grid_Y)
    
    rbf_thick = Rbf(ves_clean[col_x], ves_clean[col_y], ves_clean['Aquifer_Thickness_m'], function='multiquadric', smooth=0.1)
    predicted_thickness = rbf_thick(grid_X, grid_Y) * (1.0 + (corr_weight * 0.4 * flow_norm))

    # أسطح الارتفاعات للنمذجة ثلاثية الأبعاد
    surface_z = dem_data
    water_table_z = surface_z - predicted_depth
    aquifer_bottom_z = water_table_z - predicted_thickness

    st.session_state['predicted_res'] = predicted_resistivity
    st.session_state['surface_z'] = surface_z
    st.session_state['water_table_z'] = water_table_z
    st.session_state['aquifer_bottom_z'] = aquifer_bottom_z
    st.session_state['grid_X'] = grid_X
    st.session_state['grid_Y'] = grid_Y
    st.session_state['ves_clean'] = ves_clean
    st.session_state['col_x'] = col_x
    st.session_state['col_y'] = col_y
    st.session_state['col_z'] = col_z

    st.success("✅ تم بناء النموذج التنبؤي للحوض بالكامل!")

# ---------------------------------------------------------
# TAB 3: النمذجة ثلاثية الأبعاد والمقاطع الطباقية (3D Stratigraphy)
# ---------------------------------------------------------
with tab_3d_strat:
    st.subheader("🧊 النماذج ثلاثية الأبعاد الحقيقية للطبقات العميقة والمياه")

    ves_clean = st.session_state.get('ves_clean', pd.DataFrame())
    col_x = st.session_state.get('col_x', 'X')
    col_y = st.session_state.get('col_y', 'Y')
    col_z = st.session_state.get('col_z', 'Z')

    if 'surface_z' in st.session_state:
        # رسم النموذج 3D المكتمل
        fig_3d = go.Figure()

        # 1. سطح الأرض (DEM)
        fig_3d.add_trace(go.Surface(
            x=st.session_state['grid_X'], y=st.session_state['grid_Y'], z=st.session_state['surface_z'],
            colorscale='Greens', opacity=0.35, showscale=False, name='سطح الأرض'
        ))

        # 2. منسوب المياه الجوفية التنبؤي (Water Table)
        fig_3d.add_trace(go.Surface(
            x=st.session_state['grid_X'], y=st.session_state['grid_Y'], z=st.session_state['water_table_z'],
            surfacecolor=st.session_state['predicted_res'], colorscale='Jet_r', opacity=0.75,
            colorbar=dict(title="المقاومية التنبؤية (Ohm.m)"), name='سطح المياه الجوفية'
        ))

        # 3. قاع الطبقة الحاملة (Aquifer Bedrock)
        fig_3d.add_trace(go.Surface(
            x=st.session_state['grid_X'], y=st.session_state['grid_Y'], z=st.session_state['aquifer_bottom_z'],
            colorscale='YlOrBr', opacity=0.45, showscale=False, name='قاعدة الخزان (الأساس)'
        ))

        # 4. إضافة أسهم/نقاط الجسات الميدانية
        fig_3d.add_trace(go.Scatter3d(
            x=ves_clean[col_x], y=ves_clean[col_y], z=ves_clean[col_z],
            mode='markers+text',
            marker=dict(size=8, color='red', symbol='diamond'),
            text=ves_clean.index.astype(str), name='مواقع الجسات الميدانية'
        ))

        fig_3d.update_layout(
            scene=dict(
                xaxis_title='X (متر)', yaxis_title='Y (متر)', zaxis_title='الارتفاع Z (متر)',
                aspectratio=dict(x=1, y=1, z=0.4)
            ),
            template="plotly_dark", height=650, margin=dict(l=0, r=0, b=0, t=30)
        )

        st.plotly_chart(fig_3d, use_container_width=True)

        st.markdown("---")
        st.markdown("### 📐 مقطع طولي تنبؤي لمسار المجرى الجوفي (Hydrogeological Dynamic Cross-Section)")

        # استخراج مقطع طولي عبر الوادي (وسط الشبكة)
        mid_idx = ny // 2
        section_x = st.session_state['grid_X'][mid_idx, :]
        section_topo = st.session_state['surface_z'][mid_idx, :]
        section_wt = st.session_state['water_table_z'][mid_idx, :]
        section_bot = st.session_state['aquifer_bottom_z'][mid_idx, :]

        fig_section = go.Figure()
        fig_section.add_trace(go.Scatter(x=section_x, y=section_topo, mode='lines', name='سطح الأرض (DEM)', line=dict(color='brown', width=3)))
        fig_section.add_trace(go.Scatter(x=section_x, y=section_wt, mode='lines', name='سطح المياه الجوفية', line=dict(color='blue', width=2, dash='dash')))
        fig_section.add_trace(go.Scatter(x=section_x, y=section_bot, mode='lines', name='قاع الطبقة الحاملة', line=dict(color='black', width=2)))

        fig_section.update_layout(
            title="مقطع هيدروجيولوجي ممتد بناءً على نتائج التنبؤ الميداني والفضائي",
            xaxis_title="الإحداثي الشرقي (X)", yaxis_title="الارتفاع Z (متر)", height=400, template="plotly_white"
        )
        st.plotly_chart(fig_section, use_container_width=True)

# ---------------------------------------------------------
# TAB 4: الخرائط التنبؤية المتقدمة والتصدير
# ---------------------------------------------------------
with tab_export:
    st.subheader("🗺️ خرائط احتمالية ونطاقات جودة المياه الجوفية الممتدة")

    if 'predicted_res' in st.session_state:
        col_exp1, col_exp2 = st.columns(2)

        with col_exp1:
            fig_thick = px.imshow(
                (st.session_state['water_table_z'] - st.session_state['aquifer_bottom_z']),
                x=gx, y=gy, origin='lower',
                color_continuous_scale='Viridis',
                title="خريطة سمك الطبقة الحاملة للتكوين (Aquifer Thickness Map - m)"
            )
            st.plotly_chart(fig_thick, use_container_width=True)

        with col_exp2:
            fig_res_map = px.imshow(
                st.session_state['predicted_res'],
                x=gx, y=gy, origin='lower',
                color_continuous_scale='Jet_r',
                title="خريطة توزيع المقاومية الكهربائية التنبؤية للطبقة المائية (Ohm.m)"
            )
            st.plotly_chart(fig_res_map, use_container_width=True)

        st.markdown("---")
        st.markdown("### 📥 تصدير نتائج التنبؤ الجيوفيزيائي إلى KML")

        def export_kml(df, cx, cy):
            kml = ET.Element('kml', xmlns="http://www.opengis.net/kml/2.2")
            doc = ET.SubElement(kml, 'Document')
            folder = ET.SubElement(doc, 'Folder')
            ET.SubElement(folder, 'name').text = "نقاط الجسات الميدانية"
            for idx, r in df.iterrows():
                pm = ET.SubElement(folder, 'Placemark')
                ET.SubElement(pm, 'name').text = f"VES Point #{idx+1}"
                ET.SubElement(ET.SubElement(pm, 'Point'), 'coordinates').text = f"{r[cx]},{r[cy]},0"
            return ET.tostring(kml, encoding='utf-8')

        st.download_button(
            label="🌍 تحميل خريطة الأهداف إلى Google Earth (KML)",
            data=export_kml(ves_clean, col_x, col_y),
            file_name="HydroGeo_Extrapolated_Targets.kml",
            mime="application/vnd.google-earth.kml+xml",
            type="primary"
        )
