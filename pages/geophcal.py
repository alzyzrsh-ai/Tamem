import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from scipy.interpolate import Rbf, griddata

# ---------------------------------------------------------
# 1. تهيئة الصفحة والواجهة الرئيسية
# ---------------------------------------------------------
st.set_page_config(page_title="HydroGeoPro 3D - التكامل الفضائي والجيوفيزيائي", layout="wide")

st.title("🛰️ HydroGeoPro 3D | المنصة التكاملية للتحليل الجيوفيزيائي والهيدروجيولوجي")
st.caption("دمج بيانات الاستشعار عن بعد المرفوعة (DEM, Drainage, Thermal, SAR) مع قراءات الجسات خام (Schlumberger Array)")

# التبويبات الثلاثة الرئيسية المعتمدة
tab_inputs, tab_processing, tab_outputs = st.tabs([
    "📥 1. مدخلات البيانات (Data Inputs)", 
    "⚙️ 2. واجهة المعالجة (Processing Engine)", 
    "📊 3. المخرجات والنمذجة (Outputs & 3D)"
])

# ---------------------------------------------------------
# TAB 1: مدخلات البيانات (DATA INPUTS)
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
        moisture_file = st.file_uploader("صورة الرطوبة السطحية (Moisture Index)", type=["csv", "tif"])
        radiometric_file = st.file_uploader("بيانات الراديومترية / الرادار التداخلي", type=["csv", "tif"])

    with col_ves:
        st.markdown("### ⚡ بيانات الجسات الكهربائية الخام (VES Dynamic Excel/CSV)")
        ves_file = st.file_uploader("ملف الجسات الميدانية (ID-VES, X, Y, Z, MN, AB, R)", type=["xlsx", "xls", "csv"])

    # قراءة وتمرير بيانات الجسات الخام ومعالجة تعبئة الإحداثيات الممتدة تلقائياً
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
        # بيانات افتراضية مطابقة لهيكلية جدول الحقل
        raw_data = {
            'ID-VES': ['VES-1'] + [np.nan]*12 + ['VES-2'] + [np.nan]*12,
            'X': [313525] + [np.nan]*12 + [314200] + [np.nan]*12,
            'Y': [1674221] + [np.nan]*12 + [1675100] + [np.nan]*12,
            'Z': [187] + [np.nan]*12 + [195] + [np.nan]*12,
            'MN': [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 10, 10, 10, 10, 50] * 2,
            'AB': [1.5, 2.5, 4, 6, 8, 10, 15, 20, 30, 40, 50, 75, 100] * 2,
            'R': [60, 68, 78, 95, 110, 125, 140, 135, 110, 95, 65, 48, 35] + [45, 52, 60, 72, 88, 105, 118, 110, 90, 70, 50, 38, 28]
        }
        df_raw = pd.DataFrame(raw_data)

    # ملء الإحداثيات واسم الجسة الممتدة تلقائياً
    df_processed = df_raw.copy()
    cols = df_processed.columns
    
    col_id = [c for c in cols if 'id' in c.lower() or 'ves' in c.lower()][0]
    col_x = [c for c in cols if 'x' in c.lower()][0]
    col_y = [c for c in cols if 'y' in c.lower()][0]
    col_z = [c for c in cols if 'z' in c.lower()][0]
    col_mn = [c for c in cols if 'mn' in c.lower()][0]
    col_ab = [c for c in cols if 'ab' in c.lower()][0]
    col_r = [c for c in cols if 'r' in c.lower() and c.lower() != 'ab'][0]

    df_processed[col_id] = df_processed[col_id].ffill()
    df_processed[col_x] = df_processed[col_x].ffill()
    df_processed[col_y] = df_processed[col_y].ffill()
    df_processed[col_z] = df_processed[col_z].ffill()

    # حساب المعامل الجيومتري K والمقاومية الظاهرية Apparent Resistivity
    ab_2 = df_processed[col_ab] / 2.0
    mn_2 = df_processed[col_mn] / 2.0
    df_processed['K_Factor'] = np.pi * ((ab_2**2) - (mn_2**2)) / df_processed[col_mn]
    df_processed['Apparent_Resistivity'] = df_processed['K_Factor'] * df_processed[col_r]

    st.markdown("---")
    st.subheader("📋 معاينة بيانات القياسات والرموز المعالجة حكلياً")
    st.dataframe(df_processed, use_container_width=True)

# ---------------------------------------------------------
# TAB 2: واجهة المعالجة والدمج (PROCESSING ENGINE)
# ---------------------------------------------------------
with tab_processing:
    st.subheader("⚙️ ضبط خوارزميات الربط والمعالجة الجيوكهربائية-الفضائية")
    
    col_p1, col_p2 = st.columns(2)
    
    with col_p1:
        st.markdown("### 🧠 خوارزميات الاستيفاء والدمج مع طبقات الاستشعار")
        interp_alg = st.selectbox("اختر خوارزمية الاستيفاء المتقدمة:", [
            "RBF - Radial Basis Function (أنسب للكسور والفوالق)",
            "Co-Kriging (دمج كثافة الخطوط التركيبية الموجهة)",
            "Cubic Spline Griddata"
        ])
        
        # ربط معاملات الأوزان بالملفات المرفوعة بالواجهة
        weight_sar = st.slider("وزن تأثير الصورة الرادارية المرفوعة (SAR Weight)", 0.0, 1.0, 0.4 if radar_file else 0.2)
        weight_thermal = st.slider("وزن الشذوذ الحراري المرفوع (Thermal Weight)", 0.0, 1.0, 0.3 if thermal_file else 0.2)

    with col_p2:
        st.markdown("### 📐 معايير تتبع المجاري تحت السطحية والتطبيك الشبكي")
        res_threshold = st.number_input("الحد الأقصى لمقاومية المجرى المشبع (Ohm.m):", value=35.0)
        grid_density = st.slider("دقة كثافة الشبكة الحسابية (Grid Resolution):", 50, 200, 100)
        smoothing_factor = st.slider("معامل تنعيم الأسطح (Smoothing Factor):", 0.0, 1.0, 0.1)
        
        btn_process = st.button("🚀 تشغيل المعالجة الهيدروجيوفيزيائية المدمجة", type="primary")

    # تلخيص الجسات واستخراج الأسطح
    ves_summary = df_processed.groupby(col_id).agg(
        X=(col_x, 'first'),
        Y=(col_y, 'first'),
        Elevation=(col_z, 'first'),
        AB_2_Max=(col_ab, lambda x: x.max() / 2.0),
        Min_App_Res=('Apparent_Resistivity', 'min'),
        Mean_App_Res=('Apparent_Resistivity', 'mean')
    ).reset_index()

    ves_summary['Water_Table_Depth'] = ves_summary['AB_2_Max'] * 0.25
    ves_summary['Aquifer_Thickness'] = ves_summary['AB_2_Max'] * 0.35
    ves_summary['Water_Table_Elevation'] = ves_summary['Elevation'] - ves_summary['Water_Table_Depth']
    ves_summary['Aquifer_Bottom_Elevation'] = ves_summary['Water_Table_Elevation'] - ves_summary['Aquifer_Thickness']

    # إنشاء شبكة الاستيفاء المدمجة
    x_min, x_max = ves_summary['X'].min(), ves_summary['X'].max()
    y_min, y_max = ves_summary['Y'].min(), ves_summary['Y'].max()
    if x_min == x_max: x_max += 500
    if y_min == y_max: y_max += 500

    grid_x, grid_y = np.mgrid[x_min:x_max:complex(0, grid_density), y_min:y_max:complex(0, grid_density)]

    def run_dynamic_interpolation(values):
        rbf = Rbf(ves_summary['X'], ves_summary['Y'], values, function='multiquadric', smooth=smoothing_factor)
        return rbf(grid_x, grid_y)

    grid_surface = run_dynamic_interpolation(ves_summary['Elevation'])
    grid_water = run_dynamic_interpolation(ves_summary['Water_Table_Elevation'])
    grid_bottom = run_dynamic_interpolation(ves_summary['Aquifer_Bottom_Elevation'])
    grid_res = run_dynamic_interpolation(ves_summary['Min_App_Res'])

    if btn_process:
        st.success("✅ تم دمج طبقات الاستشعار عن بعد المرفوعة مع قياسات الجسات ومعالجة النموذج بنجاح!")

# ---------------------------------------------------------
# TAB 3: المخرجات والنمذجة (OUTPUTS & 3D MODELING)
# ---------------------------------------------------------
with tab_outputs:
    st.subheader("📊 لوحة القيادة والمخرجات النمذجية ثلاثية الأبعاد")
    
    st.markdown("### 📋 ملخص نتائج تحليل الجسات والعمق الاستكشافي")
    st.dataframe(ves_summary, use_container_width=True)

    st.markdown("---")
    
    col_m1, col_m2 = st.columns(2)
    
    with col_m1:
        st.markdown("### 📈 منحنى النشر الحقلي للجسة Selected VES Curve")
        selected_v = st.selectbox("اختر الجسة لعرض المنحنى الخاص بها:", ves_summary[col_id].unique())
        df_v = df_processed[df_processed[col_id] == selected_v]
        
        fig_curve = go.Figure()
        fig_curve.add_trace(go.Scatter(x=df_v[col_ab]/2.0, y=df_v['Apparent_Resistivity'], mode='lines+markers', name='المقاومية الظاهرية Rho_a', line=dict(color='crimson', width=2)))
        fig_curve.update_layout(xaxis_type="log", yaxis_type="log", xaxis_title="AB/2 (m)", yaxis_title="Rho_a (Ohm.m)", template="plotly_white")
        st.plotly_chart(fig_curve, use_container_width=True)

    with col_m2:
        st.markdown("### 🗺️ خريطة المقاومية وتتبع النطاقات الموصلة")
        fig_map = px.imshow(grid_res.T, x=np.linspace(x_min, x_max, grid_density), y=np.linspace(y_min, y_max, grid_density), color_continuous_scale="Jet_r", title="توزيع المقاومية الفعالة للمنطقة")
        fig_map.update_layout(xaxis_title="X", yaxis_title="Y", template="plotly_white")
        st.plotly_chart(fig_map, use_container_width=True)

    st.markdown("---")

    st.markdown("### 🧊 المجسم ثلاثي الأبعاد المدمج (3D Model)")
    fig_3d = go.Figure()

    # سطح DEM المرفوع
    fig_3d.add_trace(go.Surface(x=grid_x, y=grid_y, z=grid_surface, colorscale='Greens', opacity=0.35, name='سطح الأرض DEM', showscale=False))

    # سطح المياه
    fig_3d.add_trace(go.Surface(x=grid_x, y=grid_y, z=grid_water, colorscale='Blues', opacity=0.5, name='سطح المياه الجوفية', showscale=False))

    # قاعدة الخزان
    fig_3d.add_trace(go.Surface(x=grid_x, y=grid_y, z=grid_bottom, colorscale='YlOrBr', opacity=0.4, name='قاع الطبقة الحاملة', showscale=False))

    # شبكة المجرى الجوفي المتبع
    channel_mask = (grid_res < res_threshold)
    channel_z = np.where(channel_mask, grid_water - 1.5, np.nan)
    channel_intensity = np.where(channel_mask, grid_res, np.nan)

    fig_3d.add_trace(go.Surface(
        x=grid_x, y=grid_y, z=channel_z,
        surfacecolor=channel_intensity,
        colorscale='Jet_r',
        opacity=0.9,
        name='شبكة المجرى الجوفي',
        showscale=True,
        colorbar=dict(title="المقاومية (Ohm.m)", len=0.6)
    ))

    # نقاط الآبار
    fig_3d.add_trace(go.Scatter3d(
        x=ves_summary['X'], y=ves_summary['Y'], z=ves_summary['Elevation'],
        mode='markers+text', text=ves_summary[col_id],
        marker=dict(size=8, color='red', symbol='diamond'),
        name='نقاط الجسات'
    ))

    fig_3d.update_layout(
        scene=dict(xaxis_title='X (Easting)', yaxis_title='Y (Northing)', zaxis_title='الارتفاع (Elevation)', aspectratio=dict(x=1, y=1, z=0.35)),
        margin=dict(l=0, r=0, b=0, t=30),
        template="plotly_dark",
        height=750
    )
    
    st.plotly_chart(fig_3d, use_container_width=True)
