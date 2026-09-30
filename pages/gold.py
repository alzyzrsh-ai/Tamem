import streamlit as st
import ee
import geemap.foliumap as geemap
import json

# 1. إعدادات صفحة Streamlit
st.set_page_config(page_title="مؤشرات الذهب المتقدمة", layout="wide")
st.title("🛰️ استكشاف مؤشرات الذهب - منطقة مسجد لباده")

# 2. تهيئة Google Earth Engine
try:
    # للعمل في Streamlit Cloud عبر Secrets أو محلياً
    if "GEE_SERVICE_ACCOUNT" in st.secrets:
        service_account_info = json.loads(st.secrets["GEE_SERVICE_ACCOUNT"])
        credentials = ee.ServiceAccountCredentials(
            service_account_info["client_email"],
            key_data=st.secrets["GEE_SERVICE_ACCOUNT"]
        )
        ee.Initialize(credentials)
    else:
        ee.Initialize()
except Exception as e:
    st.error(f"خطأ في الاتصال بـ Earth Engine: {e}")

# 3. تحديد منطقة الدراسة (حول مسجد لباده والأودية المجاورة)
center_lon, center_lat = 44.1522, 15.3120
center_point = ee.Geometry.Point([center_lon, center_lat])
aoi = center_point.buffer(2500)

# 4. جلب مرئيات Sentinel-2 والمعالجة الطيفية
s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
      .filterBounds(aoi)
      .filterDate('2025-01-01', '2026-09-30')
      .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 5))
      .median()
      .clip(aoi))

iron_oxide = s2.select('B4').divide(s2.select('B2')).rename('Iron_Oxide')
clay_alteration = s2.select('B11').divide(s2.select('B12')).rename('Clay_Alteration')
silica_index = s2.select('B11').divide(s2.select('B8A')).rename('Silica_Index')

# 5. المرئيات الحرارية Landsat 8/9
landsat = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
           .filterBounds(aoi)
           .filterDate('2025-01-01', '2026-09-30')
           .filter(ee.Filter.lt('CLOUD_COVER', 5))
           .median()
           .clip(aoi))
thermal_band = landsat.select('ST_B10').rename('Thermal_Infrared')

# 6. بيانات الرادار Sentinel-1 (المجاري المطمورة)
s1_radar = (ee.ImageCollection('COPERNICUS/S1_GRD')
            .filterBounds(aoi)
            .filter(ee.Filter.eq('instrumentMode', 'IW'))
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
            .median()
            .select('VV')
            .clip(aoi))
radar_channels = s1_radar.focal_mean(50, 'circle', 'meters').rename('Radar_Channels')

# 7. التضاريس والمصايد (ALOS DEM)
dem = ee.Image('JAXA/ALOS/AW3D30/V3_2').select('DSM').clip(aoi)
slope = ee.Terrain.slope(dem)
gold_traps = slope.gte(1).And(slope.lte(3)).rename('Gold_Traps')

# 8. دمج المؤشرات الشامل
comprehensive_gold_score = (
    iron_oxide.multiply(0.25)
    .add(clay_alteration.multiply(0.20))
    .add(silica_index.multiply(0.15))
    .add(thermal_band.multiply(0.15))
    .add(radar_channels.multiply(0.15))
    .add(gold_traps.multiply(0.10))
).rename('Comprehensive_Gold_Index')

# 9. إنشاء الخريطة التفاعلية واستدعاء الطبقات
Map = geemap.Map(center=[center_lat, center_lon], zoom=14)

# إضافة الطبقة البصرية الطبيعية
Map.addLayer(s2.select(['B4', 'B3', 'B2']), {'min': 0, 'max': 3000}, 'صورة بصرية (RGB)')

# إضافة خريطة الشذوذات والمؤشرات التجميعية للذهب
vis_params = {
    'min': 0.2,
    'max': 0.8,
    'palette': ['blue', 'cyan', 'green', 'yellow', 'red']
}
Map.addLayer(comprehensive_gold_score, vis_params, 'خريطة مؤشر الذهب الشامل')

# 10. الخطوة الحاسمة: عرض الخريطة داخل واجهة Streamlit!
st.write("### الخريطة التفاعلية لمؤشرات ومصايد الذهب الرسوبي:")
Map.to_streamlit(height=650)
