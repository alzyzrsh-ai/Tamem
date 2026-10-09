import json
import ee
import streamlit as st

# 1. إعداد واجهة الصفحة
st.set_page_config(
    page_title="المنصة الفضائية المتقدمة لمعالجة الشذوذات المعدنية والهيدرولوجية",
    page_icon="🛰️",
    layout="wide",
)

st.title("🛰️ المنصة الفضائية المتقدمة لمعالجة الشذوذات المعدنية والهيدرولوجية")
st.markdown(
    "نظام معالجة سحابي مدمج (Multi-Sensor Satellite Prospectivity Engine) للاستكشاف المعدني والهيدرولوجي مع دعم التنزيل للـ GIS."
)

# 2. تهيئة وتوثيق Google Earth Engine
PROJECT_ID = "lively-armor-507414-s8"


@st.cache_resource
def init_earth_engine():
  try:
    if "GEE_SERVICE_ACCOUNT" in st.secrets:
      gee_secret = st.secrets["GEE_SERVICE_ACCOUNT"]
      if isinstance(gee_secret, str):
        cleaned_secret = gee_secret.replace("\r", "").replace("\t", " ")
        try:
          key_dict = json.loads(cleaned_secret, strict=False)
        except Exception:
          key_dict = json.loads(
              cleaned_secret.replace("\n", "\\n"), strict=False
          )
      else:
        key_dict = dict(gee_secret)

      if "private_key" in key_dict and isinstance(
          key_dict["private_key"], str
      ):
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")

      project_name = key_dict.get("project_id", PROJECT_ID)
      credentials = ee.ServiceAccountCredentials(
          key_dict["client_email"], key_data=json.dumps(key_dict)
      )
      ee.Initialize(credentials, project=project_name)
      return True, "تم الاتصال بنجاح بخوادم Google Earth Engine!"
    else:
      ee.Initialize(project=PROJECT_ID)
      return True, "تم الاتصال بالحساب الافتراضي!"
  except Exception as e:
    return False, f"فشل الاتصال: {str(e)}"


gee_ok, gee_msg = init_earth_engine()

if not gee_ok:
  st.error(gee_msg)
  st.stop()
else:
  st.sidebar.success(f"✅ GEE Connected ({PROJECT_ID})")

# 3. لوحة المدخلات الجانبية
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
    "نصف قطر نطاق الدراسة (كيلومتر):",
    min_value=1.0,
    max_value=10.0,
    value=2.0,
    step=0.5,
)

point = ee.Geometry.Point([target_lon, target_lat])
aoi = point.buffer(buffer_km * 1000)
region = aoi.bounds().getInfo()["coordinates"]

st.sidebar.markdown("---")
st.sidebar.header("🎛 خيارات المعالجة والتحليل")
show_sentinel_rgb = st.sidebar.checkbox(
    "صورة ألوان طبيعية Sentinel-2 RGB", value=True
)
show_iron = st.sidebar.checkbox(
    "نطاقات أكسيد الحديد (Iron Oxide Ratio)", value=True
)
show_clay = st.sidebar.checkbox(
    "التحول الطيني (Hydroxyl / Clay Alteration)", value=True
)
show_silica = st.sidebar.checkbox(
    "مؤشر السليكا والكوارتز (Landsat 8 SWIR)", value=True
)
show_slope = st.sidebar.checkbox(
    "انحدار المجرى والمصايد (ALOS DEM Slope)", value=True
)

st.write(
    f"### 🛰️ نتائج التحليل الفضائي والتصدير للـ GIS (Lat: {target_lat}, Lon:"
    f" {target_lon})"
)


# دالة لتوليد الصورة الثابتة ورابط تنزيل بصيغة GeoTIFF
def display_and_download_ee_image(image_obj, vis_params, title_text, file_prefix):
  try:
    with st.spinner(f"جاري معالجة وتجهيز: {title_text}..."):
      # 1. توليد رابط المعاينة كصورة
      thumb_url = image_obj.getThumbURL({
          "region": region,
          "dimensions": 600,
          "format": "jpg",
          **vis_params,
      })
      st.subheader(title_text)
      st.image(thumb_url, use_container_width=True)

      # 2. توليد رابط تحميل ملف الـ GeoTIFF لبرامج GIS
      download_url = image_obj.getDownloadURL({
          "name": file_prefix,
          "region": aoi,
          "scale": 10,  # دقة البكسل 10 متر
          "format": "GEO_TIFF",
      })
      st.markdown(
          f"📥 [تحميل الطبقة بصيغة GeoTIFF لبرامج الـ GIS]({download_url})"
      )
      st.markdown("---")
  except Exception as e:
    st.warning(f"تعذر معالجة {title_text}: {str(e)}")


# 4. معالجة وعرض الطبقات مع روابط التحميل
if show_sentinel_rgb:
  s2 = (
      ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
      .filterBounds(aoi)
      .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
      .sort("CLOUD_COVER")
      .first()
      .clip(aoi)
  )
  display_and_download_ee_image(
      s2.select(["B4", "B3", "B2"]),
      {"min": 0, "max": 3000},
      "📷 صورة ألوان طبيعية Sentinel-2 RGB",
      "Sentinel_RGB",
  )

if show_iron:
  s2_iron = (
      ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
      .filterBounds(aoi)
      .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
      .sort("CLOUD_COVER")
      .first()
      .clip(aoi)
  )
  iron_ratio = (
      s2_iron.select("B4")
      .divide(s2_iron.select("B2"))
      .rename("Iron_Oxide")
  )
  display_and_download_ee_image(
      iron_ratio,
      {
          "min": 1.1,
          "max": 2.2,
          "palette": ["blue", "yellow", "orange", "red"],
      },
      "🔥 نطاق أكسيد الحديد (Iron Oxide)",
      "Iron_Oxide_Ratio",
  )

if show_clay:
  s2_clay = (
      ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
      .filterBounds(aoi)
      .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
      .sort("CLOUD_COVER")
      .first()
      .clip(aoi)
  )
  clay_ratio = (
      s2_clay.select("B11")
      .divide(s2_clay.select("B12"))
      .rename("Clay_Alteration")
  )
  display_and_download_ee_image(
      clay_ratio,
      {
          "min": 1.0,
          "max": 2.0,
          "palette": ["black", "cyan", "green", "magenta"],
      },
      "🧪 التحول الطيني (Hydroxyl / Clay)",
      "Clay_Alteration",
  )

if show_silica:
  l8 = (
      ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
      .filterBounds(aoi)
      .sort("CLOUD_COVER")
      .first()
      .clip(aoi)
  )
  silica_index = (
      l8.select("SR_B6").divide(l8.select("SR_B7")).rename("Silica_Index")
  )
  display_and_download_ee_image(
      silica_index,
      {"min": 0.8, "max": 1.8, "palette": ["brown", "white", "purple"]},
      "💎 مؤشر السليكا والكوارتز (Landsat SWIR)",
      "Silica_Index",
  )

if show_slope:
  dem = ee.Image("JAXA/ALOS/AW3D30/V1_1").select("AVE").clip(aoi)
  slope = ee.Terrain.slope(dem).rename("Slope")
  display_and_download_ee_image(
      slope,
      {
          "min": 0,
          "max": 45,
          "palette": ["green", "yellow", "orange", "red"],
      },
      "⛰️ انحدار المجرى والمصايد (ALOS DEM Slope)",
      "DEM_Slope",
  )
