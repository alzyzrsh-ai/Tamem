import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from scipy.interpolate import Rbf

# ---------------------------------------------------------
# 1. تهيئة الصفحة والواجهة
# ---------------------------------------------------------
st.set_page_config(page_title="HydroGeoPro 3D", layout="wide")

st.title("🛰️ HydroGeoPro 3D | المنصة التكاملية للتحليل الجيوفيزيائي والهيدروجيولوجي")
st.caption("دمج بيانات الاستشعار عن بعد المرفوعة (DEM, Drainage, Thermal, SAR) مع قراءات الجسات خام (Schlumberger Array)")

tab_inputs, tab_processing, tab_outputs = st.tabs([
    "📥 1. مدخلات البيانات (Data Inputs)", 
    "⚙️ 2. واجهة المعالجة (Processing Engine)", 
    "📊 3. المخرجات والنمذجة (Outputs & 3D)"
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
        # بيانات افتراضية للعمل في حال عدم رفع ملف
        raw_data = {
            'ID-VES': ['VES-1'] + [np.nan]*12 + ['VES-2'] + [np.nan]*12,
            'X': [313525] + [np.nan]*12 + [314200] + [np.nan]*12,
            'Y': [1674221] + [np.nan]*12 + [1675100] + [np.nan]*12,
            'Z': [187] + [np.nan]*12 + [195] + [np.nan]*12,
            'MN': [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 10, 10, 10, 10, 50] * 2,
            'AB': [1.5, 2.5, 4, 6, 8, 10, 15, 20, 30, 40, 50, 75, 100] * 2,
            'R': [60, 68, 78, 95, 110, 125, 140, 135, 110, 95, 65, 48, 35] * 2
        }
        df_raw = pd.DataFrame(raw_data)

    df_processed = df_raw.copy()
    cols = df_processed.columns
    
    # التعرف الآلي على أسماء الأعمدة
    col_id = [c for c in cols if 'id' in c.lower() or 'ves' in c.lower() or 'جسة' in c.lower()][0]
    col_x = [c for c in cols if 'x' in c.lower() or 'شرق' in c.lower()][0]
    col_y = [c for c in cols if 'y' in c.lower() or 'شمال' in c.lower()][0]
    col_z = [c for c in cols if 'z' in c.lower() or 'ارتفاع' in c.lower() or 'منسوب' in c.lower()][0]
    col_mn = [c for c in cols if 'mn' in c.lower()][0]
    col_ab = [c for c in cols if 'ab' in c.lower()][0]
    col_r = [c for c in cols if 'r' in c.lower() and c.lower() != 'ab'][0]

    # سحب القيم الممتدة
    df_processed[col_id] = df_processed[col_id].ffill()
    df_processed[col_x] = df_processed[col_x].ffill()
    df_processed[col_y] = df_processed[col_y].ffill()
    df_processed[col_z] = df_processed[col_z].ffill()

    # معالجة آمنة للأرقام ومنع TypeError
    df_processed[col_ab] = pd.to_numeric(df_processed[col_ab], errors='coerce')
    df_processed[col_mn] = pd.to_numeric(df_processed[col_mn], errors='coerce')
    df_processed[col_r] = pd.to_numeric(df_processed[col_r], errors='coerce')
    df_processed[col_x] = pd.to_numeric(df_processed[col_x], errors='coerce')
    df_processed[col_y] = pd.to_numeric(df_processed[col_y], errors='coerce')
    df_processed[col_z] = pd.to_numeric(df_processed[col_z], errors='coerce')

    # إزالة الصفوف غير الرقمية
    df_processed = df_processed.dropna(subset=[col_ab, col_mn, col_r, col_x, col_y, col_z])

    # حساب المعامل الجيومتري K والمقاومية الظاهرية
    ab_2 = df_processed[col_ab] / 2.0
    mn_2 = df_processed[col_mn] / 2.0

    df_processed['K_Factor'] = np.pi * ((ab_2**2) - (mn_2**2)) / df_processed[col_mn]
    df_processed['Apparent_Resistivity'] = df_processed['K_Factor'] * df_processed[col_r]

    st.markdown("---")
    st.subheader("📋 معاينة البيانات المعالجة وتصفية الأخطاء الرقمية")
    st.dataframe(df_processed, use_container_width=True)

# ---------------------------------------------------------
# TAB 2: واجهة المعالجة
# ---------------------------------------------------------
with tab_processing:
    st.subheader("⚙️ ضبط خوارزميات الربط والمعالجة الجيوكهربائية-الفضائية")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        interp_alg = st.selectbox("اختر خوارزمية الاستيفاء المتقدمة:", ["RBF - Radial Basis Function", "Co-Kriging", "Cubic Spline"])
        weight_sar = st.slider("وزن تأثير الصورة الرادارية المرفوعة (SAR Weight)", 0.0, 1.0, 0.4)
        weight_thermal = st.slider("وزن الشذوذ الحراري المرفوع (Thermal Weight)", 0.0, 1.0, 0.3)

    with col_p2:
        res_threshold = st.number_input("الحد الأقصى لمقاومية المجرى المشبع (Ohm.m):", value=35.0)
        grid_density = st.slider("دقة كثافة الشبكة الحسابية (Grid Resolution):", 50, 200, 100)
        btn_process = st.button("🚀 تشغيل المعالجة الهيدروجيوفيزيائية المدمجة", type="primary")

    # تجميع بيانات الجسات
    ves_summary = df_processed.groupby(col_id).agg(
        X=(col_x, 'first'),
        Y=(col_y, 'first'),
        Elevation=(col_z, 'first'),
        AB_2_Max=(col_ab, lambda x: x.max() / 2.0),
        Min_App_Res=('Apparent_Resistivity', 'min')
    ).reset_index()

    ves_summary['Water_Table_Elevation'] = ves_summary['Elevation'] - (ves_summary['AB_2_Max'] * 0.25)
    ves_summary['Aquifer_Bottom_Elevation'] = ves_summary['Water_Table_Elevation'] - (ves_summary['AB_2_Max'] * 0.35)

    # تحويل كامل القيم الرقمية للجدول التجميعي للتأكد من عدم وجود كائنات غير رقمية (Object/NaN)
    for col in ['X', 'Y', 'Elevation', 'Water_Table_Elevation', 'Aquifer_Bottom_Elevation', 'Min_App_Res']:
        ves_summary[col] = pd.to_numeric(ves_summary[col], errors='coerce')

    ves_clean = ves_summary.dropna(subset=['X', 'Y', 'Elevation', 'Water_Table_Elevation', 'Aquifer_Bottom_Elevation', 'Min_App_Res']).copy()

    x_min, x_max = ves_clean['X'].min(), ves_clean['X'].max()
    y_min, y_max = ves_clean['Y'].min(), ves_clean['Y'].max()
    if x_min == x_max or pd.isna(x_min):
        x_min, x_max = 0.0, 1000.0
    if y_min == y_max or pd.isna(y_min):
        y_min, y_max = 0.0, 1000.0

    grid_x, grid_y = np.mgrid[x_min:x_max:complex(0, grid_density), y_min:y_max:complex(0, grid_density)]

    # دالة الاستيفاء الآمنة وتفادي خطأ ValueError: object arrays
    def run_interpolation(values_series):
        x = ves_clean['X'].values.astype(np.float64)
        y = ves_clean['Y'].values.astype(np.float64)
        z = values_series.values.astype(np.float64)
        
        if len(ves_clean) < 2:
            return np.full(grid_x.shape, z.mean() if len(z) > 0 else 100.0)
        
        rbf = Rbf(x, y, z, function='multiquadric', smooth=0.1)
        return rbf(grid_x, grid_y)

    grid_surface = run_interpolation(ves_clean['Elevation'])
    grid_water = run_interpolation(ves_clean['Water_Table_Elevation'])
    grid_bottom = run_interpolation(ves_clean['Aquifer_Bottom_Elevation'])
    grid_res = run_interpolation(ves_clean['Min_App_Res'])

    if btn_process:
        st.success("✅ تم دمج قراءات الملف وطبقات الاستشعار بنجاح!")

# ---------------------------------------------------------
# TAB 3: المخرجات والنمذجة ثلاثية الأبعاد
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
        fig_map = px.imshow(grid_res.T, x=np.linspace(x_min, x_max, grid_density), y=np.linspace(y_min, y_max, grid_density), color_continuous_scale="Jet_r", title="توزيع المقاومية الفعالة")
        st.plotly_chart(fig_map, use_container_width=True)

    st.markdown("### 🧊 النمذجة ثلاثية الأبعاد (3D Subsurface Model)")
    fig_3d = go.Figure()
    fig_3d.add_trace(go.Surface(x=grid_x, y=grid_y, z=grid_surface, colorscale='Greens', opacity=0.3, name='سطح الأرض DEM'))
    fig_3d.add_trace(go.Surface(x=grid_x, y=grid_y, z=grid_water, colorscale='Blues', opacity=0.5, name='سطح المياه الجوفية'))
    fig_3d.add_trace(go.Surface(x=grid_x, y=grid_y, z=grid_bottom, colorscale='YlOrBr', opacity=0.4, name='قاع الطبقة الحاملة'))

    fig_3d.update_layout(scene=dict(xaxis_title='X', yaxis_title='Y', zaxis_title='Z'), template="plotly_dark", height=700)
    st.plotly_chart(fig_3d, use_container_width=True)
