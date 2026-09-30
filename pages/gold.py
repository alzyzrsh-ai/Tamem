import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
import json

st.set_page_config(page_title="مؤشرات الذهب المتقدمة", layout="wide")
st.title("🛰️ استكشاف مؤشرات الذهب - منطقة مسجد لباده")

# 1. تهيئة Google Earth Engine
try:
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

# 2. تحديد منطقة الدراسة
center_lon, center_lat = 44.1522, 15.3120
center_point = ee.Geometry.Point([center_lon, center_lat])
aoi = center_point.buffer(2500)

# 3. Sentinel-2 والمعالجة الطيفية
s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
      .filterBounds(aoi)
      .filterDate('2025-01-01', '2026-09-30')
      .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 5))
      .median()
      .clip(aoi))

iron_oxide = s2.select('B4').divide(s2.select('B2'))
clay_alteration = s2.select('B11').divide(s2.select('B12'))
silica_index = s2.select('B11').divide(s2.select('B8A'))

# 4. الحراري Landsat 8/9
landsat = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
           .filterBounds(aoi)
           .filterDate('2025-01-01', '2026-09-30')
           .filter(ee.Filter.lt('CLOUD_COVER', 5))
           .median()
           .clip(aoi))
thermal_band = landsat.select('ST_B10')

# 5. الرادار Sentinel-1
s1_radar = (ee.ImageCollection('COPERNICUS/S1_GRD')
            .filterBounds(aoi)
            .filter(ee.Filter.eq('instrumentMode', 'IW'))
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
            .median()
            .select('VV')
            .clip(aoi))
radar_channels = s1_radar.focal_mean(50, 'circle', 'meters')

# 6. التضاريس ALOS DEM
dem = ee.Image('JAXA/ALOS/AW3D30/V3_2').select('DSM').clip(aoi)
slope = ee.Terrain.slope(dem)
gold_traps = slope.gte(1).And(slope.lte(3))

# 7. دمج المؤشرات
comprehensive_gold_score = (
    iron_oxide.multiply(0.25)
    .add(clay_alteration.multiply(0.20))
    .add(silica_index.multiply(0.15))
    .add(thermal_band.multiply(0.15))
    .add(radar_channels.multiply(0.15))
    .add(gold_traps.multiply(0.10))
)

# دالة تحويل طبقة GEE إلى رابط Tile لعرضها في Folium
def add_ee_layer(self, ee_image_object, vis_params, name):
    map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
    folium.TileLayer(
        tiles=map_id_dict['tile_fetcher'].url_format,
        attr='Google Earth Engine',
        name=name,
        overlay=True,
        control=True
    ).add_to(self)

folium.Map.add_ee_layer = add_ee_layer

# 8. إنشاء الخريطة
m = folium.Map(location=[center_lat, center_lon], zoom_start=14)

# إضافة الطبقات
m.add_ee_layer(
    s2.select(['B4', 'B3', 'B2']), 
    {'min': 0, 'max': 3000}, 
    'صورة بصرية (RGB)'
)

vis_params = {
    'min': 0.2,
    'max': 0.8,
    'palette': ['blue', 'cyan', 'green', 'yellow', 'red']
}
m.add_ee_layer(comprehensive_gold_score, vis_params, 'خريطة مؤشر الذهب الشامل')

folium.LayerControl().add_to(m)

# 9. عرض الخريطة في Streamlit
st.write("### الخريطة التفاعلية لمؤشرات ومصايد الذهب الرسوبي:")
st_folium(m, width=1100, height=650)
