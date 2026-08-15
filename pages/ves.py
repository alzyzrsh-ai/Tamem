import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import json

# ضبط إعدادات الصفحة
st.set_page_config(
    page_title="تحليل الجسات والجيوكهرباء",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ دمج الجسات الجيوكهربائية (VES) مع البيانات الفضائية")
st.markdown("---")

# ==========================================
# 1. الاتصال الآمن بـ Google Earth Engine
# ==========================================
ee_connected = False
ee_module = None

try:
    import ee
    # محاولة المصادقة فقط إذا كانت المفاتيح متوفرة في Secrets
    if "gcp_service_account" in st.secrets:
        service_account_info = json.loads(st.secrets["gcp_service_account"])
        credentials = ee.ServiceAccountCredentials(
            service_account_info['client_email'],
            key_data=json.dumps(service_account_info)
        )
        ee.Initialize(credentials)
        ee_connected = True
        ee_module = ee
    else:
        # محاولة تهيئة بديلة دون التعطيل
        ee.Initialize()
        ee_connected = True
        ee_module = ee
except Exception as e:
    ee_connected = False

# تنبيه للمستخدم بحالة الاتصال
if ee_connected:
    st.success("✅ تم الاتصال بـ Google Earth Engine بنجاح!")
else:
    st.info("💡 يتم الآن عرض تحليل الجسة الميدانية محلياً (الاتصال الفضائي يتطلب ضبط مفاتيح Earth Engine في Streamlit Secrets).")

# ==========================================
# 2. البيانات الميدانية للجسة (VES No. 2)
# ==========================================
st.subheader("📊 بيانات الجسة الميدانية (VES No. 2)")

utm_easting = 330407
utm_northing = 1558564
elevation_masl = 208

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown(f"""
    **معلومات الموقع:**
    * **الإحداثيات:** UTM-E `{utm_easting}` | UTM-N `{utm_northing}`
    * **المنسوب:** `{elevation_masl}` م فوق سطح البحر
    * **الترتيب المستعمل:** شلومبرجير (Schlumberger)
    """)

# جدول القراءات الميدانية
ves2_data = {
    'MN/2 (m)': [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 10.0, 0.5, 10.0, 10.0, 
                 10.0, 10.0, 10.0, 50.0, 10.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0],
    'AB/2 (m)': [1.5, 2.5, 4.0, 6.0, 8.0, 10.0, 15.0, 20.0, 30.0, 40.0, 40.0, 50.0, 
                 75.0, 100.0, 160.0, 150.0, 200.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0],
    'Rho_a (Ohm.m)': [428.3, 382.6, 369.5, 319.8, 330.0, 349.3, 342.8, 315.4, 311.3, 302.2, 
                      245.3, 210.0, 166.7, 135.8, 68.2, 73.0, 50.0, 38.1, 15.2, 14.9, 16.5, 25.1, 10.6, 22.4]
}

df_ves = pd.DataFrame(ves2_data)

# حساب متوسط المقاومية الفعالة للطبقة العميقة
deep_aquifer_rho = df_ves[df_ves['AB/2 (m)'] >= 200]['Rho_a (Ohm.m)'].mean()

with col1:
    st.metric(label="متوسط مقاومية النطاق المشبع (AB/2 ≥ 200m)", value=f"{deep_aquifer_rho:.2f} Ohm.m")
    st.dataframe(df_ves.head(8), use_container_width=True)

# رسم منحنى الجسة Log-Log Plot
with col2:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.loglog(df_ves['AB/2 (m)'], df_ves['Rho_a (Ohm.m)'], 'ro-', label='VES No. 2 المقاس')
    ax.set_xlabel('نصف مسافة الأقطاب AB/2 (متر)')
    ax.set_ylabel('المقاومية الظاهرية Rho_a (أوم.متر)')
    ax.set_title('منحنى الجسة الجيوكهربائية (Log-Log)')
    ax.grid(True, which="both", ls="--", alpha=0.6)
    ax.legend()
    st.pyplot(fig)

st.markdown("---")

# ==========================================
# 3. معالجة وتدريب النموذج (معزل آمن)
# ==========================================
st.subheader("🤖 النمذجة والربط بالتعلم الآلي (Machine Learning)")

if ee_connected and ee_module is not None:
    try:
        lon, lat = 43.4295812, 14.0931013
        ves_point = ee_module.Geometry.Point([lon, lat])
        roi = ves_point.buffer(5000)

        sar = ee_module.ImageCollection('COPERNICUS/S1_GRD') \
                .filterBounds(roi) \
                .filter(ee_module.Filter.listContains('transmitterReceiverPolarisation', 'VV')) \
                .select('VV').mean().clip(roi)

        landsat = ee_module.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
                    .filterBounds(roi) \
                    .filter(ee_module.Filter.lt('CLOUD_COVER', 15)).median()

        lst = landsat.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15).clip(roi)
        dem = ee_module.Image('USGS/SRTMGL1_003').clip(roi)
        slope = ee_module.Terrain.slope(dem)

        stack = ee_module.Image.cat([sar.rename('SAR_VV'), lst.rename('LST'), dem.rename('ELEVATION'), slope.rename('SLOPE')])
        
        features = stack.reduceRegion(reducer=ee_module.Reducer.first(), geometry=ves_point, scale=30).getInfo()
        
        st.write("📌 **المؤشرات الفضائية المستخرجة عند موقع الجسة:**")
        st.json(features)

    except Exception as e:
        st.warning(f"تعذر جلب الطبقات الفضائية: {e}")
else:
    st.write("📊 **وضع المعالجة المحلي متفعل:** التطبيق يعرض المنحنيات والحسابات الجيوكهربائية للجسة الميدانية بنجاح دون أي توقف.")
