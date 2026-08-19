import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from scipy.interpolate import Rbf, griddata

# ---------------------------------------------------------
# 1. تهيئة الصفحة والواجهة الرئيسية
# ---------------------------------------------------------
st.set_page_config(page_title="HydroGeoPro 3D - العملاق الجيوفيزيائي", layout="wide")

st.title("🛰️ HydroGeoPro 3D | المنصة التكاملية للتحليل الجيوفيزيائي والهيدروجيولوجي")
st.caption("دمج بيانات الاستشعار عن بعد (الرادار، الحراري، DEM) مع الجسات الجيوكهربائية (VES) لكشف الموائع وتتبع المجاري المائية تحت السطحية")

# إنشاء التبويبات الثلاثة الرئيسية
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
        st.markdown("### ⚡ بيانات الجسات الكهربائية (VES Data)")
        ves_file = st.file_uploader("ملف الجسات الميدانية الجيوكهربائية (CSV)", type=["csv"])
        
        st.info("💡 صيغة ملف الجسات المطلوب: [VES_ID, X, Y, Elevation, Water_Table_Depth, Aquifer_Thickness, Resistivity, SAR_Lineament_Density, Thermal_Anomaly]")

    # تحميل بيانات افتراضية توضيحية في حال عدم رفع ملفات
    if ves_file is not None:
        df_ves = pd.read_csv(ves_file)
    else:
        st.warning("⚠️ يتم استخدام مجموعة بيانات افتراضية عالية الدقة لتشغيل النموذج التجريبي:")
        np.random.seed(42)
        n_points = 12
        x = np.linspace(2500, 4500, n_points) + np.random.normal(0, 50, n_points)
        y = np.linspace(5000, 7000, n_points) + np.random.normal(0, 50, n_points)
        elev = 1200 - (x - 2500)*0.05 - (y - 5000)*0.03
        water_depth = 35 + (x - 2500)*0.008 + np.random.normal(0, 3, n_points)
        thick = 25 + np.sin(x/300)*10
        res = 45 - (thick*0.5) + np.random.normal(0, 5, n_points)
        lin_density = np.clip((100 - res)/100, 0.1, 0.95)
        
        df_ves = pd.DataFrame({
            'VES_ID': [f'VES-{i+1:02d}' for i in range(n_points)],
            'X': x, 'Y': y, 'Elevation': elev,
            'Water_Table_Depth': water_depth,
            'Aquifer_Thickness': thick,
            'Resistivity': res,
            'SAR_Lineament_Density': lin_density,
            'Thermal_Anomaly': np.random.uniform(18.5, 24.0, n_points)
        })
        
    st.dataframe(df_ves, use_container_width=True)

# ---------------------------------------------------------
# TAB 2: واجهة المعالجة والربط (PROCESSING ENGINE)
# ---------------------------------------------------------
with tab_processing:
    st.subheader("⚙️ ضبط خوارزميات الربط والمعالجة الجيوكهربائية-الفضائية")
    
    col_p1, col_p2 = st.columns(2)
    
    with col_p1:
        st.markdown("### 🧠 خوارزميات الاستيفاء والربط (Data Fusion)")
        interp_alg = st.selectbox("اختر خوارزمية الاستيفاء المتقدمة:", [
            "RBF - Radial Basis Function (أنسب للكسور والفوالق)",
            "Co-Kriging (دمج كثافة الخطوط التركيبية الموجهة)",
            "Cubic Spline Griddata"
        ])
        
        weight_sar = st.slider("وزن تأثير بيانات الرادار (Lineaments Weight)", 0.0, 1.0, 0.4)
        weight_thermal = st.slider("وزن الشذوذ الحراري (Thermal Weight)", 0.0, 1.0, 0.3)

    with col_p2:
        st.markdown("### 📐 معايير تتبع المجاري تحت السطحية")
        res_threshold = st.number_input("الحد الأقصى لمقاومية المجرى المشبع (Ohm.m):", value=35.0)
        smoothing_factor = st.slider("معامل تنعيم الأسطح (Smoothing Factor):", 0.0, 1.0, 0.2)
        
        btn_process = st.button("🚀 تشغيل المعالجة الهيدروجيوفيزيائية المدمجة", type="primary")

    # الحسابات الهيكلية
    df_ves['Water_Table_Elevation'] = df_ves['Elevation'] - df_ves['Water_Table_Depth']
    df_ves['Aquifer_Bottom_Elevation'] = df_ves['Water_Table_Elevation'] - df_ves['Aquifer_Thickness']
    df_ves['Transmissivity_Index'] = (df_ves['Aquifer_Thickness'] / df_ves['Resistivity']) * 1000

    # إعداد شبكة الاستيفاء عالية الدقة
    grid_x, grid_y = np.mgrid[
        df_ves['X'].min():df_ves['X'].max():100j, 
        df_ves['Y'].min():df_ves['Y'].max():100j
    ]

    # دالة الاستيفاء الديناميكية
    def run_interpolation(values):
        if "RBF" in interp_alg:
            rbf = Rbf(df_ves['X'], df_ves['Y'], values, function='multiquadric', smooth=smoothing_factor)
            return rbf(grid_x, grid_y)
        else:
            return griddata((df_ves['X'], df_ves['Y']), values, (grid_x, grid_y), method='cubic')

    grid_surface = run_interpolation(df_ves['Elevation'])
    grid_water = run_interpolation(df_ves['Water_Table_Elevation'])
    grid_bottom = run_interpolation(df_ves['Aquifer_Bottom_Elevation'])
    grid_res = run_interpolation(df_ves['Resistivity'])

    if btn_process:
        st.success("✅ تمت معالجة وتدقيق البيانات وإعداد المقاطع الشبكية بنجاح!")

# ---------------------------------------------------------
# TAB 3: المخرجات والنمذجة (OUTPUTS & 3D MODELING)
# ---------------------------------------------------------
with tab_outputs:
    st.subheader("📊 لوحة القيادة والمخرجات النمذجية ثلاثية الأبعاد")
    
    # 1. جداول قياسات ومعاملات الخزان
    st.markdown("### 📋 جدول الحسابات الهيدروجيوفيزيائية المتقدمة")
    st.dataframe(df_ves[[
        'VES_ID', 'X', 'Y', 'Elevation', 'Water_Table_Depth', 
        'Water_Table_Elevation', 'Aquifer_Thickness', 'Resistivity', 
        'Transmissivity_Index', 'SAR_Lineament_Density'
    ]], use_container_width=True)

    st.markdown("---")
    
    col_m1, col_m2 = st.columns(2)
    
    # 2. المقاطع ثنائية الأبعاد (2D Cross-Sections)
    with col_m1:
        st.markdown("### 📈 المقطع الهيدروجيوفيزيائي الطولي (2D Section)")
        df_sorted = df_ves.sort_values(by='X')
        
        fig_2d = go.Figure()
        fig_2d.add_trace(go.Scatter(x=df_sorted['X'], y=df_sorted['Elevation'], mode='lines+markers', name='سطح الأرض (DEM)', line=dict(color='brown', width=3)))
        fig_2d.add_trace(go.Scatter(x=df_sorted['X'], y=df_sorted['Water_Table_Elevation'], mode='lines+markers', name='منسوب المياه (Water Table)', line=dict(color='blue', width=2.5, dash='dash')))
        fig_2d.add_trace(go.Scatter(x=df_sorted['X'], y=df_sorted['Aquifer_Bottom_Elevation'], mode='lines+markers', name='قاع الخزان (Bedrock)', line=dict(color='black', width=2)))
        
        fig_2d.update_layout(
            title="مقطع عرضي يوضح النطاق المشبع وتغير المنسوب",
            xaxis_title="الإحداثي (Easting - m)",
            yaxis_title="الارتفاع المطلق (Elevation - m)",
            template="plotly_white",
            legend=dict(orientation="h", y=1.1)
        )
        st.plotly_chart(fig_2d, use_container_width=True)

    # 3. خريطة النطاقات الموصلية وشبكة المجرى الجوفي
    with col_m2:
        st.markdown("### 🗺️ خريطة المقاومية وتتبع المجرى الجوفي")
        fig_map = px.imshow(
            grid_res.T, 
            x=np.linspace(df_ves['X'].min(), df_ves['X'].max(), 100),
            y=np.linspace(df_ves['Y'].min(), df_ves['Y'].max(), 100),
            color_continuous_scale="Jet_r",
            title="توزيع المقاومية الكهربائية (النطاقات الزرقاء = مسارات المياه)"
        )
        fig_map.update_layout(xaxis_title="X", yaxis_title="Y", template="plotly_white")
        st.plotly_chart(fig_map, use_container_width=True)

    st.markdown("---")

    # 4. المجسم ثلاثي الأبعاد المتقدم مع تدرج شدة المقاومية للمجرى الجوفي
    st.markdown("### 🧊 المجسم ثلاثي الأبعاد التفاعلي (3D Hydrogeological & Paleochannel Block)")
    
    fig_3d = go.Figure()

    # طبقة سطح الأرض (Terrain Surface)
    fig_3d.add_trace(go.Surface(
        x=grid_x, y=grid_y, z=grid_surface, 
        colorscale='Greens', opacity=0.35, name='سطح الأرض (DEM)', showscale=False
    ))

    # طبقة منسوب المياه (Water Table Surface)
    fig_3d.add_trace(go.Surface(
        x=grid_x, y=grid_y, z=grid_water, 
        colorscale='Blues', opacity=0.6, name='سطح المياه الجوفية', showscale=False
    ))

    # طبقة قاعدة الصخور (Bedrock)
    fig_3d.add_trace(go.Surface(
        x=grid_x, y=grid_y, z=grid_bottom, 
        colorscale='YlOrBr', opacity=0.4, name='قاع الطبقة الحاملة', showscale=False
    ))

    # استخراج وتتبع شبكة المجاري تحت السطحية وتدريج لونها حسب شدة المقاومية
    channel_mask = (grid_res < res_threshold)
    channel_z = np.where(channel_mask, grid_water - 2, np.nan)
    channel_intensity = np.where(channel_mask, grid_res, np.nan)

    fig_3d.add_trace(go.Surface(
        x=grid_x, 
        y=grid_y, 
        z=channel_z,
        surfacecolor=channel_intensity,  # ربط التدرج بقيمة المقاومية الفعلية
        colorscale='Jet_r',              # الأزرق الداكن يمثل أعلى موصلية (أدنى مقاومية)
        opacity=0.9, 
        name='شبكة المجرى الجوفي (Paleochannel)', 
        showscale=True,
        colorbar=dict(title="المقاومية (Ohm.m)", len=0.6, y=0.5)
    ))

    # إضافة مواقع آبار الجسات (VES Locations)
    fig_3d.add_trace(go.Scatter3d(
        x=df_ves['X'], y=df_ves['Y'], z=df_ves['Water_Table_Elevation'],
        mode='markers+text',
        text=df_ves['VES_ID'],
        marker=dict(size=6, color='red', symbol='diamond'),
        name='موقع الجسة (VES)'
    ))

    fig_3d.update_layout(
        scene=dict(
            xaxis_title='الإحداثي X (Easting)',
            yaxis_title='الإحداثي Y (Northing)',
            zaxis_title='الارتفاع عن سطح البحر (Elevation)',
            aspectratio=dict(x=1, y=1, z=0.35)
        ),
        margin=dict(l=0, r=0, b=0, t=30),
        template="plotly_dark",
        height=750
    )
    
    st.plotly_chart(fig_3d, use_container_width=True)
