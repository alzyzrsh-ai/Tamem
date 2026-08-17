import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata

# 1. إعدادات الصفحة
st.set_page_config(
    page_title="الجسات المجاورة والقطاعات الجيوكهربائية",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ تحليلات الجسات المجاورة والقطاع الرأسي (2D Section)")
st.markdown("---")

# 2. بيانات الجسات الجيوكهربائية الميدانية (VES 1, VES 2, VES 3)
ab2_distances = [1.5, 2.5, 4.0, 6.0, 8.0, 10.0, 15.0, 20.0, 30.0, 40.0, 50.0, 75.0, 100.0, 150.0, 200.0, 300.0, 400.0, 500.0]

ves_database = {
    'AB/2 (m)': ab2_distances,
    'VES-1 (مقاومية)': [380.0, 350.1, 310.2, 290.0, 260.5, 240.0, 210.0, 180.3, 140.0, 95.0, 70.0, 45.2, 30.0, 22.0, 18.5, 12.0, 11.5, 15.0],
    'VES-2 (مقاومية)': [428.3, 382.6, 369.5, 319.8, 330.0, 349.3, 342.8, 315.4, 311.3, 245.3, 210.0, 166.7, 135.8, 73.0, 38.1, 15.2, 14.9, 16.5],
    'VES-3 (مقاومية)': [510.0, 460.0, 410.2, 380.5, 350.0, 310.0, 280.0, 250.0, 190.0, 130.0, 90.0, 60.0, 42.0, 28.0, 21.0, 17.5, 18.0, 22.0]
}

df_multi_ves = pd.DataFrame(ves_database)

# مواضع الجسات الميدانية بالأمتار على خط المسار (Profile Distance)
ves_positions = {'VES-1': 0, 'VES-2': 250, 'VES-3': 500}

# 3. عرض المقارنة المنحنية للجسات الثلاث
st.subheader("📈 مقارنة منحنيات الجسات المجاورة")
col_left, col_right = st.columns([1, 2])

with col_left:
    st.markdown("**مواقع الجسات على المسار:**")
    for name, pos in ves_positions.items():
        st.write(f"• **{name}:** عند المسافة `{pos} متر`")
    
    st.dataframe(df_multi_ves, use_container_width=True, height=280)

with col_right:
    fig_curves, ax_curves = plt.subplots(figsize=(7, 4))
    ax_curves.loglog(df_multi_ves['AB/2 (m)'], df_multi_ves['VES-1 (مقاومية)'], 'b-o', label='VES-1 (0m)')
    ax_curves.loglog(df_multi_ves['AB/2 (m)'], df_multi_ves['VES-2 (مقاومية)'], 'r-o', label='VES-2 (250m)')
    ax_curves.loglog(df_multi_ves['AB/2 (m)'], df_multi_ves['VES-3 (مقاومية)'], 'g-o', label='VES-3 (500m)')
    
    ax_curves.set_xlabel('AB/2 (m)')
    ax_curves.set_ylabel('Apparent Resistivity (Ohm.m)')
    ax_curves.grid(True, which="both", linestyle="--", alpha=0.5)
    ax_curves.legend()
    st.pyplot(fig_curves)
    plt.close(fig_curves)

st.markdown("---")

# 4. بناء القطاع الجيوكهربائي الثنائي الأبعاد (2D Pseudo-Section)
st.subheader("🗺️ المقطع الجيوكهربائي الرأسي (2D Pseudo-Section)")

# إعداد شبكة الاستيفاء (Interpolation Grid)
x_coords = []
z_coords = []
rho_values = []

for name, pos in ves_positions.items():
    col_name = f"{name} (مقاومية)"
    for ab2, rho in zip(df_multi_ves['AB/2 (m)'], df_multi_ves[col_name]):
        x_coords.append(pos)
        z_coords.append(ab2)  # AB/2 يعكس عمق التغلغل الظاهري
        rho_values.append(rho)

grid_x, grid_z = np.mgrid[0:500:100j, min(ab2_distances):max(ab2_distances):100j]
grid_rho = griddata((x_coords, z_coords), rho_values, (grid_x, grid_z), method='cubic')

fig_sec, ax_sec = plt.subplots(figsize=(10, 4.5))
contour = ax_sec.contourf(grid_x, grid_z, grid_rho, levels=20, cmap='jet_r')
cbar = fig_sec.colorbar(contour, ax=ax_sec)
cbar.set_label('Apparent Resistivity (Ohm.m)', rotation=270, labelpad=15)

# تحديد مواقع الجسات على المقطع
for name, pos in ves_positions.items():
    ax_sec.axvline(x=pos, color='black', linestyle='--', alpha=0.7)
    ax_sec.text(pos, min(ab2_distances)-5, name, horizontalalignment='center', fontweight='bold')

ax_sec.set_ylim(max(ab2_distances), min(ab2_distances))  # عكس المحور الرأسي ليمثل العمق
ax_sec.set_xlabel('Profile Distance (m)')
ax_sec.set_ylabel('Pseudo-Depth / (AB/2 in meters)')
ax_sec.set_title('Cross-Section across VES-1, VES-2, and VES-3')

st.pyplot(fig_sec)
plt.close(fig_sec)

st.info("💡 **القراءة الهيدروجيولوجية للمقطع:** المناطق ذات المقاومية المنخفضة (باللون الأزرق $\le 20\ \Omega\cdot\text{m}$) تمثل نطاقات التشبع المائي الرئيسية وتوضح امتداد الخزان الجوفي بين الجسات.")
