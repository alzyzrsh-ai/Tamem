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
st.markdown("نظام معالجة سحابي متكامل بصيغة إطار مربع، مؤشر اتجاه الشمال المدمج، وتصدير المتجهات الميدانية.")

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
                    key_dict = json.loads(cleaned_secret.replace("\n", "\\n"), strict=False)
            else:
                key_dict = dict(gee_secret)
            
            if "private_key" in key_dict and isinstance(key_dict["private_key"], str):
                key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
                
            project_name = key_dict.get("project_id", PROJECT_ID)
            credentials = ee.ServiceAccountCredentials(key_dict["client_email"], key_data=json.dumps(key_dict))
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

target_lat = st.sidebar.number_input("خط العرض (Latitude):", value=default_lat, format="%.6f")
target_lon = st.sidebar.number_input("خط الطول (Longitude):", value=default_lon, format="%.6f")
buffer_km = st.sidebar.slider("نصف قطر نطاق الدراسة (كيلومتر):", min_value=1.0, max_value=10.0, value=2.0, step=0.5)

# تحويل مسافة الكيلومتر إلى نطاق إحداثي مربع (Bounding Box) لتغطية كامل المربع بدون أطراف سوداء
delta = buffer_km / 111.0  # تقريب الدرجات الجغرافية مقابل الكيلومتر
aoi = ee.Geometry.Rectangle([
    target_lon - delta,
    target_lat - delta,
    target_lon + delta,
    target_lat + delta
])
region = aoi.bounds().getInfo()["coordinates"]

st.sidebar.markdown("---")
st.sidebar.header("🎛 خيارات المعالجة والطبقات")
show_sentinel_rgb = st.sidebar.checkbox("صورة ألوان طبيعية Sentinel-2 RGB", value=True)
show_swir_composite = st.sidebar.checkbox("صورة الأشعة تحت الحمراء SWIR Composite", value=True)
show_iron = st.sidebar.checkbox("نطاق أكسيد الحديد (Iron Oxide)", value=True)
show_clay = st.sidebar.checkbox("التحول الطيني (Clay/SWIR)", value=True)
show_silica = st.sidebar.checkbox("مؤشر السليكا والكوارتز (Landsat SWIR)", value=True)
show_thermal = st.sidebar.checkbox("الانبعاث الحراري (Thermal LST)", value=True)
show_slope = st.sidebar.checkbox("انحدار المجرى (DEM Slope)", value=True)

# تبويبات التطبيق الرئيسية
tab1, tab2, tab3 = st.tabs([
    "🛰️ العرض والتحميل الفضائي", 
    "📊 نافذة المعالجة الحقيقية والإحصائيات", 
    "📍 استخراج وتصدير المتجهات (KML لـ AlpineQuest)"
])

with tab1:
    st.write(f"### 🛰️ الصور الفضائية بصيغة إطار مربع ومؤشر الشمال المدمج - Lat: {target_lat}, Lon: {target_lon}")

    def display_and_download_ee_image(image_obj, vis_params, title_text, file_prefix, scale_res):
        try:
            with st.spinner(f"جاري معالجة وتجهيز: {title_text}..."):
                thumb_url = image_obj.getThumbURL({
                    "region": region,
                    "dimensions": "800x800",
                    "format": "jpg",
                    **vis_params
                })
                st.subheader(title_text)
                
                # عرض الصورة مع مؤشر اتجاه الشمال الإرشادي المدمج بأناقة داخل الإطار باستخدام HTML/CSS
                st.markdown(f"""
                    <div style="position: relative; display: inline-block; width: 100%;">
                        <img src="{thumb_url}" style="width: 100%; border-radius: 8px; border: 2px solid #ccc;">
                        <div style="position: absolute; top: 15px; right: 15px; background: rgba(0, 0, 0, 0.75); color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold; font-family: sans-serif; font-size: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">
                            🧭 N ⬆️
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                st.caption(f"📐 **الدقة المكانية (Scale):** {scale_res} | 📊 **التدرج اللوني (من الأدنى إلى الأعلى Min -> Max):** {vis_params.get('min')} ⬅️ إلى ➡️ {vis_params.get('max')}")
                
                download_url = image_obj.getDownloadURL({
                    "name": file_prefix,
                    "region": aoi,
                    "scale": int(scale_res.replace(" متر", "").replace("متر", "")),
                    "format": "GEO_TIFF"
                })
                st.markdown(f"📥 [تحميل الطبقة بصيغة GeoTIFF للـ GIS]({download_url})")
                st.markdown("---")
        except Exception as e:
            st.warning(f"تعذر معالجة {title_text}: {str(e)}")

    if show_sentinel_rgb:
        s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(aoi).filter(ee.Filter.lt("CLOUDY_
