import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ضبط إعدادات الصفحة
st.set_page_config(
    page_title="تحليل الجسات الجيوكهربائية",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ دمج الجسات الجيوكهربائية (VES) مع البيانات الفضائية")
st.markdown("---")

# البيانات الميدانية للجسة (VES No. 2)
utm_easting = 330407
utm_northing = 1558564
elevation_masl = 208

ves2_data = {
    'MN/2 (m)': [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 10.0, 0.5, 10.0, 10.0, 
                 10.0, 10.0, 10.0, 50.0, 10.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0],
    'AB/2 (m)': [1.5, 2.5, 4.0, 6.0, 8.0, 10.0, 15.0, 20.0, 30.0, 40.0, 40.0, 50.0, 
                 75.0, 100.0, 160.0, 150.0, 200.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0],
    'Rho_a (Ohm.m)': [428.3, 382.6, 369.5, 319.8, 330.0, 349.3, 342.8, 315.4, 311.3, 302.2, 
                      245.3, 210.0, 166.7, 135.8, 68.2, 73.0, 50.0, 38.1, 15.2, 14.9, 16.5, 25.1, 10.6, 22.4]
}

df_ves = pd.DataFrame(ves2_data)
deep_aquifer_rho = df_ves[df_ves['AB/2 (m)'] >= 200]['Rho_a (Ohm.m)'].mean()

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📊 بيانات الموقع")
    st.write(f"**إحداثيات UTM:** `{utm_easting}` E | `{utm_northing}` N")
    st.write(f"**الارتفاع عن سطح البحر:** `{elevation_masl}` متر")
    st.metric(label="متوسط مقاومية النطاق العميق (AB/2 ≥ 200m)", value=f"{deep_aquifer_rho:.2f} Ω·m")
    st.dataframe(df_ves, use_container_width=True, height=280)

with col2:
    st.subheader("📈 منحنى الجسة الجيوكهربائية (Schlumberger)")
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.loglog(df_ves['AB/2 (m)'], df_ves['Rho_a (Ohm.m)'], 'ro-', label='VES No. 2')
    ax.set_xlabel('AB/2 (m)')
    ax.set_ylabel('Apparent Resistivity (Ohm.m)')
    ax.grid(True, which="both", linestyle="--", alpha=0.5)
    ax.legend()
    st.pyplot(fig)
    plt.close(fig)

st.markdown("---")
st.success("✅ تم تشغيل السكربت بنجاح واستقرار تام بدون الاعتماد على سيرفرات Earth Engine الخارجية.")
