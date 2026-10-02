import json
import ee
import folium
import streamlit as st
from streamlit_folium import st_folium

# 1. إعداد صفحة التطبيق
st.set_page_config(
    page_title="منصة الاستكشاف الفضائي والمعدني المتقدمة",
    page_icon="🛰️",
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
            key_dict = json.loads(st.secrets["GEE_SERVICE_ACCOUNT"])
            credentials = ee.ServiceAccountCredentials(
                key_dict["client_email"], key_data=st.secrets["GEE_SERVICE_ACCOUNT"]
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

# 3. لوحة المدخلات الجانبية (شاشة التخصيص لأي منطقة في العالم)
st.sidebar.header("🎯 إعدادات منطقة الاستكشاف")

# الإحداثيات الافتراضية (مسجد لباده كمثال بداية)
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

# 4. خوارزميات جلب ومعالجة الصور الفضائية

# أ) Sentinel-2 (الأكسيد، الطين، الألوان الطبيعية)
s2 = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(aoi)
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 15))
    .sort("CLOUD_COVER")
    .first()
    .clip(aoi)
)

# نسبة أكسيد الحديد B4/B2
iron_ratio = s2.select("B4").divide(s2.select("B2")).rename("Iron_Oxide")

# نسبة التحول الطيني B11/B12
clay_ratio = s2.select("B11").divide(s2.select("B12")).rename("Clay_Alteration")

# ب) Landsat 8 (السليكا والحراري)
l8 = (
    ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
    .filterBounds(aoi)
    .sort("CLOUD_COVER")
    .first()
    .clip(aoi)
)

# نسبة السليكا/الكوارتز (B6/B7)
silica_index = l8.select("SR_B6").divide(l8.select("SR_B7")).rename("Silica_Index")

# النطاق الحراري B10 (الانبعاث الحراري)
thermal_band = l8.select("ST_B10").multiply(0.00341802).add(149.0).rename("Thermal")

# ج) Sentinel-1 (الرادار التكتوني)
s1 = (
    ee.ImageCollection("COPERNICUS/S1_GRD")
    .filterBounds(aoi)
    .filter(ee.Filter.eq("instrumentMode", "IW"))
    .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
    .first()
    .clip(aoi)
)
sar_vv = s1.select("VV")

# د) الموديل الرقمي الهيدرولوجي ALOS DEM
dem = ee.Image("JAXA/ALOS/AW3D30/V1_1").select("AVE").clip(aoi)
slope = ee.Terrain.slope(dem).rename("Slope")

# 5. إنشاء الخريطة التفاعلية باستخدام Folium
m = folium.Map(location=[target_lat, target_lon], zoom_start=14, tiles=None)

# إعداد خريطة قاعدة من Esri Satellite
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri World Imagery",
    name="صورة فضائية عالية الدقة (Esri)",
    overlay=False,
    control=True,
).add_to(m)

# وظيفة إضافة طبقات GEE إلى Folium
def add_ee_layer(ee_image_object, vis_params, name):
    map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
    folium.TileLayer(
        tiles=map_id_dict["tile_fetcher"].url_format,
        attr="Google Earth Engine",
        name=name,
        overlay=True,
        control=True,
    ).add_to(m)

# إضافة الطبقات حسب تحديد المستخدم
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

# وضع علامة على النقطة المستهدفة
folium.Marker(
    location=[target_lat, target_lon],
    popup=f"نقطة الاستكشاف المركزية\nLat: {target_lat}, Lon: {target_lon}",
    icon=folium.Icon(color="red", icon="star"),
).add_to(m)

# إضافة التحكم بالطبقات
folium.LayerControl(collapsed=False).add_to(m)

# 6. عرض الخريطة ولوحة التحليل
st.write(f"### 🗺️ خريطة التحليل الفضائي التفاعلية لـ ({target_lat}, {target_lon})")
st_folium(m, width=1200, height=650)

# 7. دليل تفسير الشذوذات الميداني
st.markdown("---")
st.write("### 📖 دليل التفسير الجيوفيزيائي للمصايد والشذوذات:")
col1, col2, col3 = st.columns(3)

with col1:
    st.info(
        "**🔥 أكسيد الحديد والطين:**\nاللون الأحمر في أكسيد الحديد والوردي/الماجنتا في الطين يدل على نطاقات تجوية كبريتيدات الحديد وتطفر الهيدروحراري (Gossan / Alteration Zones)."
    )

with col2:
    st.success(
        "**💎 السليكا والانبعاث الحراري:**\nاللون الأرجواني/الأبيض في السليكا يوضح عروق الكوارتز والمناطق الغنية بالسليكا التي غالباً ما تحتضن تمعدنات الذهب العرقي."
    )

with col3:
    st.warning(
        "**⛰️ انحدار المجرى والمصايد:**\nتغير الانحدار من الأحمر إلى الأخضر/الأصفر يمثل نقاط انكسار المجرى (Slope Break)، وهي المصايد الرسوبية المثالية لتجمع الذهب الودي."
    )
