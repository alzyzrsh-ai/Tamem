import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
import json

# 1. إعدادات الصفحة
st.set_page_config(
    page_title="منصة الاستكشاف المعدني والفضائي المتقدمة",
    page_icon="🛰️",
    layout="wide"
)

# 2. تهيئة Earth Engine مع معالجة مفاتيح Secrets
@st.cache_resource
def init_earth_engine():
    try:
        project_id = "lively-armor-507414-s8"
        
        if "GEE_SERVICE_ACCOUNT" in st.secrets:
            sec = st.secrets["GEE_SERVICE_ACCOUNT"]
            if hasattr(sec, "to_dict"):
                secrets_dict = sec.to_dict()
            elif isinstance(sec, str):
                secrets_dict = json.loads(sec, strict=False)
            else:
                secrets_dict = dict(sec)

            if "private_key" in secrets_dict:
                pk = secrets_dict["private_key"]
                if isinstance(pk, str):
                    secrets_dict["private_key"] = pk.replace("\\n", "\n")

            credentials = ee.ServiceAccountCredentials(
                secrets_dict["client_email"],
                key_data=json.dumps(secrets_dict)
            )
            ee.Initialize(credentials, project=project_id)
        else:
            ee.Initialize(project=project_id)
            
        return True
    except Exception as e:
        st.error(f"فشل الاتصال بـ Google Earth Engine: {e}")
        return False

ee_initialized = init_earth_engine()

# 3. واجهة المستخدم والشريط الجانبي
st.title("المنصة الفضائية المتقدمة لمعالجة الشذوذات المعدنية والهيدرولوجية 🛰️")
st.caption("Multi-Sensor Satellite Prospectivity Engine - نظام استكشاف الذهب والتعدن الهيدروحراري")

st.sidebar.header("⚙️ إعدادات النطاق والتصور")
lat = st.sidebar.number_input("خط العرض (Latitude)", value=15.3120, format="%.5f")
lon = st.sidebar.number_input("خط الطول (Longitude)", value=44.1522, format="%.5f")
zoom = st.sidebar.slider("مستوى التقريب (Zoom)", min_value=6, max_value=16, value=11)
buffer_km = st.sidebar.slider("نطاق التحليل (كم)", min_value=5, max_value=50, value=15)

st.subheader(f"🗺️ خريطة التحليل الفضائي والطيفي التفاعلية ({lat:.4f}, {lon:.4f})")

# 4. بناء الخريطة والطبقات
if ee_initialized:
    try:
        point = ee.Geometry.Point([lon, lat])
        roi = point.buffer(buffer_km * 1000)

        # إنشاء خريطة Folium الأساسية
        m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles="OpenStreetMap")

        def add_ee_layer(ee_image_object, vis_params, name, show=True):
            map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
            folium.TileLayer(
                tiles=map_id_dict['tile_fetcher'].url_format,
                attr='Google Earth Engine',
                name=name,
                overlay=True,
                control=True,
                show=show
            ).add_to(m)

        # أ) ALOS DEM V3_2 - النموذج الرقمي للارتفاعات والميول
        dem = ee.ImageCollection("JAXA/ALOS/AW3D30/V3_2").select('DSM').mosaic().clip(roi)
        slope = ee.Terrain.slope(dem)
        
        add_ee_layer(dem, {'min': 500, 'max': 3000, 'palette': ['0000ff', '00ffff', 'ffff00', 'ff0000', 'ffffff']}, "النموذج الرقمي للارتفاعات (ALOS DEM V3.2)", show=False)
        add_ee_layer(slope, {'min': 0, 'max': 45, 'palette': ['white', 'black']}, "مخطط الميول والانكسارات (Slope)", show=False)

        # ب) Sentinel-2 SR - مؤشرات استكشاف الذهب
        s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
              .filterBounds(roi)
              .filterDate('2023-01-01', '2024-01-01')
              .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))
              .median()
              .clip(roi))

        iron_oxide = s2.select('B4').divide(s2.select('B2'))
        clay_alteration = s2.select('B11').divide(s2.select('B12'))
        silica_ferrous = s2.select('B12').divide(s2.select('B8'))
        gold_composite = s2.select(['B12', 'B11', 'B4'])

        add_ee_layer(gold_composite, {'min': 500, 'max': 4500}, "تركيبة استكشاف الذهب (RGB: SWIR2, SWIR1, Red)", show=True)
        add_ee_layer(iron_oxide, {'min': 1.1, 'max': 2.3, 'palette': ['blue', 'yellow', 'red']}, "شذوذات أكسيد الحديد (Gossan / Iron Oxide)", show=True)
        add_ee_layer(clay_alteration, {'min': 1.0, 'max': 2.2, 'palette': ['gray', 'cyan', 'magenta']}, "نطاقات التحول الطيني (Alunite/Kaolinite/Sericite)", show=True)
        add_ee_layer(silica_ferrous, {'min': 0.5, 'max': 1.8, 'palette': ['black', 'green', 'white']}, "مؤشر السليكا والمعادن الحديدية (Ferrous/Silica)", show=False)

        # ج) Landsat 8/9 Thermal Infrared (TIR) - الانبعاث الحراري
        l8_thermal = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
                      .filterBounds(roi)
                      .filterDate('2023-01-01', '2024-01-01')
                      .filter(ee.Filter.lt('CLOUD_COVER', 10))
                      .select('ST_B10')
                      .median()
                      .multiply(0.00341802).add(149.0)
                      .subtract(273.15)
                      .clip(roi))

        add_ee_layer(l8_thermal, {'min': 20, 'max': 50, 'palette': ['blue', 'green', 'yellow', 'orange', 'red']}, "الانبعاث الحراري (TIR Band 10 Surface Temp)", show=False)

        # أدوات التحكم وعلامة الموقع
        folium.LayerControl(collapsed=False).add_to(m)
        folium.Marker([lat, lon], popup="مرجع التحليل الحقلي").add_to(m)

        # رندر خفيف وسريع ومباشر
        st_folium(m, height=500, use_container_width=True, returned_objects=[])

    except Exception as err:
        st.error(f"خطأ في معالجة الطبقات الفضائية: {err}")
else:
    st.warning("بانتظار تهيئة Google Earth Engine...")

# 5. الدليل الجيوفيزيائي والطيفي
st.markdown("---")
st.subheader("📖 دليل التفسير الجيوفيزيائي والأدلة الطيفية للذهب:")

col1, col2 = st.columns(2)

with col1:
    st.info("🔥 **أكسيد الحديد والقبعات الحديدية (Gossan):**\nاللون الأحمر والبرتقالي يمثل نطاقات تجوية كبريتيدات الحديد (Pyrite/Chalcopyrite) التي تعلو التمعدنات الذهبية عادة.")
    st.success("💎 **نطاقات التحول الطيني الهيدروحراري (SWIR Alteration):**\nاللون الماجنتا والوردي يوضح تواجد معادن السيريسيت والكاولينيت والألونيت الناتجة عن المحاليل المائية الحارة.")

with col2:
    st.warning("⚡ **تركيبة الذهب الطيفية (SWIR2 / SWIR1 / Red):**\nتظهر المظاهر الصخرية الحاوية لعروق الكوارتز باللون الأبيض الضارب إلى الأصفر في التركيبة الثلاثية.")
    st.error("🌡️ **الانبعاث الحراري (Thermal TIR B10):**\nيساعد الفارق الحراري في تمييز الامتدادات البنيوية وعروق الكوارتز الضخمة والمجاري الهيدرولوجية القديمة.")
