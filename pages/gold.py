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
st.markdown("نظام معالجة سحابي متكامل مع أداة استخراج وتحويل الإحداثيات الميدانية.")

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

target_lat = st.sidebar.number_input("خط العرض الرئيسي (Latitude):", value=default_lat, format="%.6f")
target_lon = st.sidebar.number_input("خط الطول الرئيسي (Longitude):", value=default_lon, format="%.6f")
buffer_km = st.sidebar.slider("نصف قطر نطاق الدراسة (كيلومتر):", min_value=1.0, max_value=10.0, value=2.0, step=0.5)

delta = buffer_km / 111.0
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
tab1, tab2, tab3, tab4 = st.tabs([
    "📍 أداة استخراج وتوثيق الإحداثيات الحقلية",
    "🛰️ العرض والتحميل الفضائي", 
    "⚙️ نموذج الاحتمالية المرجح (WPI Engine)", 
    "📍 استخراج وتصدير المتجهات (KML لـ AlpineQuest)"
])

with tab1:
    st.write("### 📍 أداة تحديد وتحويل إحداثيات الأهداف الميدانية")
    st.markdown("إذا استخرجت إحداثيات أي نقطة ملفتة للانتباه من خريطة الشذوذ أو Google Earth، أدخلها هنا لتحويلها فوراً إلى نقطة توجيه (Waypoint) وتصديرها لتطبيق الـ AlpineQuest.")

    col_in1, col_in2 = st.columns(2)
    with col_in1:
        target_point_lat = st.number_input("خط العرض للنقطة المستهدفة (Target Lat):", value=target_lat, format="%.6f")
    with col_in2:
        target_point_lon = st.number_input("خط الطول للنقطة المستهدفة (Target Lon):", value=target_lon, format="%.6f")

    target_name = st.text_input("اسم النقطة أو الهدف الميداني:", value="Target_Waypoint")

    if st.button("📌 توليد نقطة التوجيه وتصديرها كملف KML"):
        try:
            pt = ee.Geometry.Point([target_point_lon, target_point_lat])
            pt_feature = ee.Feature(pt, {"name": target_name})
            fc = ee.FeatureCollection([pt_feature])

            # تصحيح دالة التصدير لتجنب خطأ الـ dict
            pt_kml_url = fc.getDownloadURL('kml')

            st.success(f"✅ تم توليد نقطة التوجيه بنجاح!")
            st.code(f"الإحداثيات المعتمدة:\nLat: {target_point_lat:.6f}\nLon: {target_point_lon:.6f}")
            st.markdown(f"📥 **[انقر هنا لتحميل ملف الـ KML الخاص بهذه النقطة لـ AlpineQuest]({pt_kml_url})**")
            st.info("💡 افتح هذا الملف مباشرة في هاتفك عبر تطبيق **AlpineQuest** أو **Google Earth** للتوجه المباشر نحو الإحداثية في الحقل.")

        except Exception as e:
            st.error(f"حدث خطأ أثناء توليد نقطة الإحداثيات: {str(e)}")

with tab2:
    st.write(f"### 🛰️ الصور الفضائية بصيغة إطار مربع واتجاه الشمال - Lat: {target_lat}, Lon: {target_lon}")

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
                st.image(thumb_url, use_container_width=True, caption="🧭 اتجاه الشمال الجغرافي نحو الأعلى (North UP ⬆️)")
                st.caption(f"📐 **الدقة المكانية (Scale):** {scale_res} | 📊 **التدرج اللوني (من الأدنى للأعلى Min -> Max):** {vis_params.get('min')} ⬅️ إلى ➡️ {vis_params.get('max')}")
                
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
        s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(aoi).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).sort("CLOUD_COVER").first().clip(aoi)
        display_and_download_ee_image(s2.select(["B4", "B3", "B2"]), {"min": 0, "max": 3000}, "📷 صورة ألوان طبيعية Sentinel-2 RGB", "Sentinel_RGB", "10 متر")

    if show_swir_composite:
        s2_swir = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(aoi).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).sort("CLOUD_COVER").first().clip(aoi)
        display_and_download_ee_image(s2_swir.select(["B11", "B8", "B4"]), {"min": 200, "max": 4500}, "📡 صورة الأشعة تحت الحمراء القصيرة (SWIR Composite B11-B8-B4)", "Sentinel_SWIR_Composite", "20 متر")

    if show_iron:
        s2_iron = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(aoi).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).sort("CLOUD_COVER").first().clip(aoi)
        iron_ratio = s2_iron.select("B4").divide(s2_iron.select("B2")).rename("Iron_Oxide")
        display_and_download_ee_image(iron_ratio, {"min": 0.8, "max": 2.5, "palette": ["blue", "yellow", "orange", "red"]}, "🔥 نطاق أكسيد الحديد (Iron Oxide - من الأدنى للأعلى)", "Iron_Oxide", "10 متر")

    if show_clay:
        s2_clay = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(
