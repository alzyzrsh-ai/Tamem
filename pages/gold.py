import json
import ee
import folium
import streamlit as st
from streamlit_folium import st_folium

# 1. إعداد شاشة الصفحة
st.set_page_config(
    page_title="استكشاف الذهب والمصايد الرسوبية",
    page_icon="👑",
    layout="wide",
)

st.title("🛰️ المنصة الفضائية المتقدمة لمعالجة الشذوذات المعدنية والهيدرولوجية")
st.markdown(
    "نظام معالجة سحابي مدمج (Multi-Sensor Satellite Prospectivity Engine) للاستكشاف عن الذهب والمعادن المصاحبة."
)

# 2. تهيئة وتوثيق Google Earth Engine باستخدام Secrets
@st.cache_resource
def init_earth_engine():
    try:
        if "GEE_SERVICE_ACCOUNT" in st.secrets:
            gee_secret = st.secrets["GEE_SERVICE_ACCOUNT"]
            
            if isinstance(gee_secret, str):
                cleaned_secret = gee_secret.replace('\r', '').replace('\t', ' ')
                try:
                    key_dict = json.loads(cleaned_secret, strict=False)
                except Exception:
                    key_dict = json.loads(cleaned_secret.replace('\n', '\\n'), strict=False)
            else:
                key_dict = dict(gee_secret)

            if "private_key" in key_dict and isinstance(key_dict["private_key"], str):
                key_dict["private_key"] = key_dict["private_key"].replace('\\n', '\n')

            credentials = ee.ServiceAccountCredentials(
                key_dict["client_email"], 
                key_data=json.dumps(key_dict)
            )
            ee.Initialize(credentials)
            return True, "تم الاتصال بنجاح بخوادم Google Earth Engine!"
        else:
            ee.Initialize()
            return True, "تم الاتصال بالحساب الافتراضي!"
    except Exception as e:
        return False, f"فشل الاتصال: {str(e)}"


gee_ok, gee_msg = init_earth_engine()

if not gee_ok:
    st.error(gee_msg)
    st.stop()
else:
    st.sidebar.success("✅ GEE Connected")

# 3. لوحة المدخلات الجانبية لأي إحداثيات في العالم
st.sidebar.header("🎯 إعدادات منطقة الاستكشاف")

default_lat = 15.3120
default_lon = 44.1522

target_lat = st.sidebar.number_input(
    "خط العرض (Latitude):", value=default_lat, format="%.6f"
)
target_lon = st.sidebar.number_input(
    "خط الطول (Longitude):", value=default_lon, format="%.6f"
)
buffer_km = st.sidebar.slider(
    "نصف قطر نطاق الدراسة (كيلومتر):", min_value=1.0, max_value=20.0, value=3.0, step=0.5
)

# تحديد المنطقة الجغرافية (AOI)
point = ee.Geometry.Point([target_lon, target_lat])
aoi = point.buffer(buffer_km * 1000)

st.sidebar.markdown("---")
st.sidebar.header("🎛️ طبقات التحليل المتاحة")
show_sentinel_rgb = st.sidebar.checkbox("صورة ألوان طبيعية Sentinel-2 RGB", value=True)
show_iron = st.sidebar.checkbox("نطاقات أكسيد الحديد (Iron Oxide Ratio)", value=True)
show_clay = st.sidebar.checkbox("التحول الطيني (Hydroxyl / Clay Alteration)", value=True)
show_silica = st.sidebar.checkbox("مؤشر السليكا والكوارتز (Landsat 8 SWIR)", value=True)
show_thermal = st.sidebar.checkbox("الانبعاثات الحرارية (Landsat TIR LST)", value=False)
show_sar = st.sidebar.checkbox("اختراق الرادار التكتوني (Sentinel-1 SAR)", value=False)
show_slope = st.sidebar.checkbox("انحدار المجرى والمصايد (ALOS DEM Slope)", value=True)

# 4. المعالجة الفضائية المباشرة
s2 = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(aoi)
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 15))
    .sort("CLOUD_COVER")
    .first()
    .clip(aoi)
)

iron_ratio = s2.select("B4").divide(s2.select("B2")).rename("Iron_Oxide")
clay_ratio = s2.select("B11").divide(s2.select("B12")).rename("Clay_Alteration")

l8 = (
    ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
    .filterBounds(aoi)
    .sort("CLOUD_COVER")
    .first()
    .clip(aoi)
)

silica_index = l8.select("SR_B6").divide(l8.select("SR_B7")).rename("Silica_Index")
thermal_band = l8.select("ST_B10").multiply(0.00341802).add(149.0).rename("Thermal")

s1 = (
    ee.ImageCollection("COPERNICUS/S1_GRD")
    .filterBounds(aoi)
    .filter(ee.Filter.eq("instrumentMode", "IW"))
    .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
    .first()
    .clip(aoi)
)
sar_vv = s1.select("VV")

dem = ee.Image("JAXA/ALOS/AW3D30/V1_1").select("AVE").clip(aoi)
slope = ee.Terrain.slope(dem).rename("Slope")

# 5. عرض الخريطة التفاعلية
m = folium.Map(location=[target_lat, target_lon], zoom_start=14, tiles=None)

folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri World Imagery",
    name="صورة فضائية عالية الدقة (Esri)",
    overlay=False,
    control=True,
).add_to(m)

def add_ee_layer(ee_image_object, vis_params, name):
    map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
    folium.TileLayer(
        tiles=map_id_dict["tile_fetcher"].url_format,
        attr="Google Earth Engine",
        name=name,
        overlay=True,
        control=True,
    ).add_to(m)

if show_sentinel_rgb:
    add_ee_layer(
        s2,
        {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000},
        "Sentinel-2 ألوان طبيعية",
    )

if show_iron:
    add_ee_layer(
        iron_ratio,
        {"min": 1.1, "max": 2.2, "palette": ["blue", "yellow", "orange", "red"]},
        "🔥 أكسيد الحديد (Iron Oxide)",
    )

if show_clay:
    add_ee_layer(
        clay_ratio,
        {"min": 1.0, "max": 2.0, "palette": ["black", "cyan", "green", "magenta"]},
        "🧪 التحول الطيني (Hydroxyl/Clay)",
    )

if show_silica:
    add_ee_layer(
        silica_index,
        {"min": 0.8, "max": 1.8, "palette": ["brown", "white", "purple"]},
        "💎 مؤشر السليكا والكوارتز",
    )

if show_thermal:
    add_ee_layer(
        thermal_band,
        {"min": 280, "max": 320, "palette": ["blue", "green", "red"]},
        "🌡️ الانبعاثات الحرارية LST",
    )

if show_sar:
    add_ee_layer(
        sar_vv,
        {"min": -25, "max": 0, "palette": ["black", "gray", "white"]},
        "📡 اختراق الرادار (Sentinel-1 SAR)",
    )

if show_slope:
    add_ee_layer(
        slope,
        {"min": 0, "max": 45, "palette": ["green", "yellow", "orange", "red"]},
        "⛰️ انحدار المجرى والمصايد (Slope)",
    )

folium.Marker(
    location=[target_lat, target_lon],
    popup=f"نقطة الاستكشاف المركزية\nLat: {target_lat}, Lon: {target_lon}",
    icon=folium.Icon(color="red", icon="star"),
).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

st.write(f"### 🗺️ خريطة التحليل الفضائي التفاعلية لـ ({target_lat}, {target_lon})")
st_folium(m, width=1200, height=650)
