import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata

st.set_page_config(page_title="رفع البيانات والقطاعات الجيوكهربائية", page_icon="⚡", layout="wide")

st.title("⚡ رفع البيانات والقطاع الجيوكهربائي الرأسي (2D Section)")
st.markdown("---")

# 1. القائمة الجانبية لرفع البيانات
st.sidebar.header("📁 رفع ملف البيانات")
uploaded_file = st.sidebar.file_uploader("ارفع ملف Excel أو CSV للجسات", type=["xlsx", "csv"])

# 2. البيانات الافتراضية
ab2_distances = [1.5, 2.5, 4.0, 6.0, 8.0, 10.0, 15.0, 20.0, 30.0, 40.0, 50.0, 75.0, 100.0, 150.0, 200.0, 300.0, 400.0, 500.0]
default_data = {
    'AB/2 (m)': ab2_distances,
    'VES-1': [380.0, 350.1, 310.2, 290.0, 260.5, 240.0, 210.0, 180.3, 140.0, 95.0, 70.0, 45.2, 30.0, 22.0, 18.5, 12.0, 11.5, 15.0],
    'VES-2': [428.3, 382.6, 369.5, 319.8, 330.0, 349.3, 342.8, 315.4, 311.3, 245.3, 210.0, 166.7, 135.8, 73.0, 38.1, 15.2, 14.9, 16.5],
    'VES-3': [510.0, 460.0, 410.2, 380.5, 350.0, 310.0, 280.0, 250.0, 190.0, 130.0, 90.0, 60.0, 42.0, 28.0, 21.0, 17.5, 18.0, 22.0]
}

# 3. معالجة البيانات المرفوعة أو استخدام الافتراضية
if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df_multi_ves = pd.read_csv(uploaded_file)
        else:
            df_multi_ves = pd.read_excel(uploaded_file)
        st.success("تم رفع الملف بنجاح! يتم استخدام بياناتك الميدانية الآن.")
    except Exception as e:
        st.error(f"خطأ في قراءة الملف: {e}")
        df_multi_ves = pd.DataFrame(default_data)
else:
    st.info("💡 يتم عرض البيانات الافتراضية حالياً. يمكنك رفع ملفك الخاص من القائمة الجانبية (Sidebar).")
    df_multi_ves = pd.DataFrame(default_data)

# 4. اختيار المسافات بين الجسات
st.sidebar.subheader("📐 المسافات بين الجسات (متر)")
ves_cols = [col for col in df_multi_ves.columns if col != 'AB/2 (m)']
ves_positions = {}

for idx, col in enumerate(ves_cols):
    ves_positions[col] = st.sidebar.number_input(f"مسافة {col}", value=idx * 250, step=50)

# 5. عرض منحنيات الجسات
st.subheader("📈 منحنيات المقاومية الظاهرية")
col_left, col_right = st.columns([1, 2])

with col_left:
    st.dataframe(df_multi_ves, use_container_width=True, height=320)

with col_right:
    fig_curves, ax_curves = plt.subplots(figsize=(7, 4.2))
    for col in ves_cols:
        ax_curves.loglog(df_multi_ves['AB/2 (m)'], df_multi_ves[col], '-o', label=f"{col} ({ves_positions[col]}m)")
    
    ax_curves.set_xlabel('AB/2 (m)')
    ax_curves.set_ylabel('Apparent Resistivity (Ohm.m)')
    ax_curves.grid(True, which="both", linestyle="--", alpha=0.5)
    ax_curves.legend()
    st.pyplot(fig_curves)
    plt.close(fig_curves)

st.markdown("---")

# 6. بناء المقطع الجيوكهربائي 2D Section
st.subheader("🗺️ المقطع الجيوكهربائي الرأسي (2D Pseudo-Section)")

x_coords, z_coords, rho_values = [], [], []

for col in ves_cols:
    pos = ves_positions[col]
    for ab2, rho in zip(df_multi_ves['AB/2 (m)'], df_multi_ves[col]):
        x_coords.append(pos)
        z_coords.append(ab2)
        rho_values.append(rho)

max_pos = max(ves_positions.values()) if max(ves_positions.values()) > 0 else 100
grid_x, grid_z = np.mgrid[0:max_pos:100j, min(df_multi_ves['AB/2 (m)']):max(df_multi_ves['AB/2 (m)']):100j]
grid_rho = griddata((x_coords, z_coords), rho_values, (grid_x, grid_z), method='cubic')

fig_sec, ax_sec = plt.subplots(figsize=(10, 4.5))
contour = ax_sec.contourf(grid_x, grid_z, grid_rho, levels=20, cmap='jet_r')
cbar = fig_sec.colorbar(contour, ax=ax_sec)
cbar.set_label('Apparent Resistivity (Ohm.m)', rotation=270, labelpad=15)

for col, pos in ves_positions.items():
    ax_sec.axvline(x=pos, color='black', linestyle='--', alpha=0.7)
    ax_sec.text(pos, min(df_multi_ves['AB/2 (m)'])-2, col, horizontalalignment='center', fontweight='bold')

ax_sec.set_ylim(max(df_multi_ves['AB/2 (m)']), min(df_multi_ves['AB/2 (m)']))
ax_sec.set_xlabel('Profile Distance (m)')
ax_sec.set_ylabel('Pseudo-Depth / (AB/2 in meters)')

st.pyplot(fig_sec)
plt.close(fig_sec)
