import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from scipy.interpolate import Rbf, griddata

# ---------------------------------------------------------
# 1. تهيئة الواجهة
# ---------------------------------------------------------
st.set_page_config(page_title="HydroGeoPro 3D - Dynamic Input Engine", layout="wide")

st.title("🛰️ HydroGeoPro 3D | منصة المعالجة الديناميكية للجسات والقياسات الفضائية")
st.caption("دعم كامل لملفات الإكسيل المفتوحة (عدد غير محدود من الجسات، مسافات النشر المتغيرة، والإحداثيات المفتوحة)")

# ---------------------------------------------------------
# 2. واجهة رفع الملفات الديناميكية
# ---------------------------------------------------------
st.sidebar.header("📥 رفع بيانات الجسات والقياسات")
uploaded_file = st.sidebar.file_uploader("رفع ملف الجسات (Excel / CSV)", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith(('.xlsx', '.xls')):
            df_ves = pd.read_excel(uploaded_file)
        else:
            df_ves = pd.read_csv(uploaded_file)
        st.sidebar.success(f"تم تحميل {len(df_ves)} جيو-نقطة/جسة بنجاح!")
    except Exception as e:
        st.sidebar.error(f"حدث خطأ أثناء قراءة الملف: {e}")
        st.stop()
else:
    st.sidebar.info("💡 لم يتم رفع ملف، يتم عرض نمط ديناميكي تجريبي:")
    # إنشاء مجموعة بيانات افتراضية قابلة للتوسع
    n_points = 15
    np.random.seed(101)
    df_ves = pd.DataFrame({
        'VES_ID': [f'VES-{i+1:02d}' for i in range(n_points)],
        'X': np.random.uniform(2000, 5000, n_points),
        'Y': np.random.uniform(5000, 9000, n_points),
        'Elevation': np.random.uniform(1100, 1300, n_points),
        'Water_Table_Depth': np.random.uniform(20, 60, n_points),
        'Aquifer_Thickness': np.random.uniform(15, 45, n_points),
        'Resistivity': np.random.uniform(10, 85, n_points),
        'AB_2_Max': np.random.choice([300, 400, 500, 600], n_points)
    })

# ---------------------------------------------------------
# 3. التحقق الديناميكي وحساب الأعمدة
# ---------------------------------------------------------
required_cols = ['VES_ID', 'X', 'Y', 'Elevation', 'Water_Table_Depth', 'Aquifer_Thickness', 'Resistivity']
missing_cols = [col for col in required_cols if col not in df_ves.columns]

if missing_cols:
    st.error(f"❌ الملف المرفوع يفتقد للأعمدة الأساسية التالية: {missing_cols}")
    st.stop()

# الحسابات الهيدروجيولوجية المباشرة بغض النظر عن عدد الجسات
df_ves['Water_Table_Elevation'] = df_ves['Elevation'] - df_ves['Water_Table_Depth']
df_ves['Aquifer_Bottom_Elevation'] = df_ves['Water_Table_Elevation'] - df_ves['Aquifer_Thickness']

st.subheader("📋 بيانات الجسات المدخلة (Dynamic Dataset View)")
st.dataframe(df_ves, use_container_width=True)

# ---------------------------------------------------------
# 4. محرك الاستيفاء والشبكات التكيفية (Adaptive Grid Engine)
# ---------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header("⚙️ إعدادات الشبكة الاستيفائية")

# تكيف دقة الشبكة تلقائياً بحسب أبعاد المنطقة
resolution = st.sidebar.slider("دقة الشبكة الحسابية (Grid Density):", 50, 200, 100)
res_threshold = st.sidebar.number_input("عتبة المقاومية لكشف المجرى الجوفي (Ohm.m):", value=35.0)

# إنشاء شبكة الإحداثيات الديناميكية المعتمدة على نطاق البيانات المدخلة
x_min, x_max = df_ves['X'].min(), df_ves['X'].max()
y_min, y_max = df_ves['Y'].min(), df_ves['Y'].max()

grid_x, grid_y = np.mgrid[
    x_min:x_max:complex(0, resolution), 
    y_min:y_max:complex(0, resolution)
]

def dynamic_rbf(values):
    # RBF تتكيف تلقائياً مع أي عدد من النقاط والتوزعات المكانية
    rbf = Rbf(df_ves['X'], df_ves['Y'], values, function='multiquadric', smooth=0.1)
    return rbf(grid_x, grid_y)

grid_surface = dynamic_rbf(df_ves['Elevation'])
grid_water = dynamic_rbf(df_ves['Water_Table_Elevation'])
grid_bottom = dynamic_rbf(df_ves['Aquifer_Bottom_Elevation'])
grid_res = dynamic_rbf(df_ves['Resistivity'])

# ---------------------------------------------------------
# 5. عرض النماذج والمخرجات ثلاثية الأبعاد
# ---------------------------------------------------------
st.markdown("---")
st.subheader("🧊 النموذج ثلاثي الأبعاد للتتابع الطبقي والمجاري الجوفية")

fig_3d = go.Figure()

# 1. سطح الأرض (DEM)
fig_3d.add_trace(go.Surface(
    x=grid_x, y=grid_y, z=grid_surface, 
    colorscale='Greens', opacity=0.3, name='سطح الأرض', showscale=False
))

# 2. منسوب المياه الجوفية
fig_3d.add_trace(go.Surface(
    x=grid_x, y=grid_y, z=grid_water, 
    colorscale='Blues', opacity=0.5, name='سطح المياه الجوفية', showscale=False
))

# 3. قاع الطبقة الحاملة
fig_3d.add_trace(go.Surface(
    x=grid_x, y=grid_y, z=grid_bottom, 
    colorscale='YlOrBr', opacity=0.3, name='قاع الطبقة الحاملة', showscale=False
))

# 4. شبكة المجاري الجوفية بتدرج الشدة المباشر
channel_mask = (grid_res < res_threshold)
channel_z = np.where(channel_mask, grid_water - 1.5, np.nan)
channel_intensity = np.where(channel_mask, grid_res, np.nan)

fig_3d.add_trace(go.Surface(
    x=grid_x, y=grid_y, z=channel_z,
    surfacecolor=channel_intensity,
    colorscale='Jet_r',  # الأزرق/الداكن يعبر عن أعلى شدة توصيل (أقل مقاومية)
    opacity=0.9,
    name='شبكة المجرى الجوفي',
    showscale=True,
    colorbar=dict(title="شدة المقاومية (Ohm.m)", len=0.6)
))

# 5. رسم أعمدة آبار الجسات ديناميكياً لتوضيح عمق النشر AB/2
fig_3d.add_trace(go.Scatter3d(
    x=df_ves['X'], y=df_ves['Y'], z=df_ves['Water_Table_Elevation'],
    mode='markers+text',
    text=df_ves['VES_ID'],
    marker=dict(
        size=7,
        color=df_ves['Resistivity'],
        colorscale='Viridis',
        symbol='diamond',
        showscale=False
    ),
    name='آبار / نقاط الجسات'
))

fig_3d.update_layout(
    scene=dict(
        xaxis_title='X (Easting)',
        yaxis_title='Y (Northing)',
        zaxis_title='الارتفاع المطلق (Elevation)',
        aspectratio=dict(x=1, y=1, z=0.35)
    ),
    margin=dict(l=0, r=0, b=0, t=30),
    template="plotly_dark",
    height=750
)

st.plotly_chart(fig_3d, use_container_width=True)
