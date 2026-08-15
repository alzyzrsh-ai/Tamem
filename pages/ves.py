import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import json

# ضبط إعدادات الصفحة في Streamlit
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
@st.cache_resource
def init_earth_engine():
    try:
        import ee
        # محاولة المصادقة عبر Streamlit Secrets
        if "gcp_service_account" in st.secrets:
            service_account_info = json.loads(st.secrets["gcp_service_account"])
            credentials = ee.ServiceAccountCredentials(
                service_account_info['client_email'],
                key_data=json.dumps(service_account_info)
            )
            ee.Initialize(credentials)
            return ee, True
        else:
            # تهيئة افتراضية
            ee.Initialize()
            return ee, True
    except Exception as e:
        return None, False

ee, ee_connected = init_earth_engine()

if ee_connected:
    st.success("✅ تم الاتصال بـ Google Earth Engine بنجاح!")
else:
    st.warning("⚠️ لم يتم تفعيل الاتصال المباشر بـ Earth Engine (تأكد من إعداد المفاتيح في Streamlit Secrets). تم تفعيل وضع التحليل الميداني المحلي.")

# ==========================================
# 2. البيانات الميدانية للجسة (VES No. 2)
# ==========================================
st.subheader("📊 بيانات الجسة الميدانية (VES No. 2)")

# بيانات الإحداثيات المرفقة
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

# حساب متوسط المقاومية الفعالة للطبقة العميقة المشبعة
deep_aquifer_rho = df_ves[df_ves['AB/2 (m)'] >= 200]['Rho_a (Ohm.m)'].mean()

with col1:
    st.metric(label="متوسط مقاومية النطاق المشبع (AB/2 ≥ 200m)", value=f"{deep_aquifer_rho:.2f} Ohm.m")

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
# 3. معالجة وتدريب نموذج التنبؤ
# ==========================================
st.subheader("🤖 النمذجة والربط بالتعلم الآلي (Machine Learning)")

if ee_connected:
    try:
        # تحويل الإحداثيات
        lon, lat = 43.4295812, 14.0931013
        ves_point = ee.Geometry.Point([lon, lat])
        roi = ves_point.buffer(5000)

        # استدعاء طبقات SAR و Landsat LST
        sar = ee.ImageCollection('COPERNICUS/S1_GRD') \
                .filterBounds(roi) \
                .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')) \
                .select('VV').mean().clip(roi)

        landsat = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
                    .filterBounds(roi) \
                    .filter(ee.Filter.lt('CLOUD_COVER', 15)).median()

        lst = landsat.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15).clip(roi)
        dem = ee.Image('USGS/SRTMGL1_003').clip(roi)
        slope = ee.Terrain.slope(dem)

        stack = ee.Image.cat([sar.rename('SAR_VV'), lst.rename('LST'), dem.rename('ELEVATION'), slope.rename('SLOPE')])
        
        # استخراج القيم بالنقطة
        features = stack.reduceRegion(reducer=ee.Reducer.first(), geometry=ves_point, scale=30).getInfo()
        
        st.write("📌 **المؤشرات الفضائية المستخرجة عند موقع الجسة:**")
        st.json(features)

    except Exception as e:
        st.error(f"حدث خطأ أثناء معالجة طبقات Earth Engine: {e}")
else:
    st.info("💡 بمجرد تفعيل مفاتيح Earth Engine، سيتم دمج المؤشرات الفضائية آلياً لإنشاء خريطة التنبؤ بالخزان الجوفي.")
