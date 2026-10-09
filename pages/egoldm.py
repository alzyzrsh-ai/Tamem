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
st.markdown("نظام معالجة سحابي حقيقي لاستخراج البيانات الجيوفيزيائية وتحليل القيم الفعلية.")

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

point = ee.Geometry.Point([target_lon, target_lat])
aoi = point.buffer(buffer_km * 1000)
region = aoi.bounds().getInfo()["coordinates"]

st.sidebar.markdown("---")
st.sidebar.header("🎛 خيارات المعالجة")
show_sentinel_rgb = st.sidebar.checkbox("صورة ألوان طبيعية Sentinel-2 RGB", value=True)
show_iron = st.sidebar.checkbox("نطاق أكسيد الحديد (Iron Oxide)", value=True)
show_clay = st.sidebar.checkbox("التحول الطيني (Clay/SWIR)", value=True)
show_silica = st.sidebar.checkbox("مؤشر السليكا والكوارتز (Landsat SWIR)", value=True)
show_thermal = st.sidebar.checkbox("الانبعاث الحراري (Thermal LST)", value=True)
show_slope = st.sidebar.checkbox("انحدار المجرى (DEM Slope)", value=True)

# تبويبات التطبيق الرئيسية
tab1, tab2 = st.tabs(["🛰️ العرض والتحميل الفضائي", "📊 نافذة معالجة البيانات الفعلية (Real GEE Analytics)"])

with tab1:
    st.write(f"### 🛰️ الصور الفضائية ومقياس الدقة المكانية (Lat: {target_lat}, Lon: {target_lon})")

    def display_and_download_ee_image(image_obj, vis_params, title_text, file_prefix, scale_res):
        try:
            with st.spinner(f"جاري معالجة وتجهيز: {title_text}..."):
                thumb_url = image_obj.getThumbURL({
                    "region": region,
                    "dimensions": 600,
                    "format": "jpg",
                    **vis_params
                })
                st.subheader(title_text)
                st.image(thumb_url, use_container_width=True)
                
                # عرض المقياس ودليل الألوان بوضوح تحت كل صورة
                st.caption(f"📐 **المقياس والدقة المكانية (Spatial Scale):** {scale_res} | 🎨 **نطاق القيم (Min/Max):** {vis_params.get('min')} إلى {vis_params.get('max')}")
                
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

    if show_iron:
        s2_iron = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(aoi).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).sort("CLOUD_COVER").first().clip(aoi)
        iron_ratio = s2_iron.select("B4").divide(s2_iron.select("B2")).rename("Iron_Oxide")
        display_and_download_ee_image(iron_ratio, {"min": 1.1, "max": 2.2, "palette": ["blue", "yellow", "orange", "red"]}, "🔥 نطاق أكسيد الحديد (Iron Oxide)", "Iron_Oxide", "10 متر")

    if show_clay:
        s2_clay = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(aoi).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).sort("CLOUD_COVER").first().clip(aoi)
        clay_ratio = s2_clay.select("B11").divide(s2_clay.select("B12")).rename("Clay_Alteration")
        display_and_download_ee_image(clay_ratio, {"min": 1.0, "max": 2.0, "palette": ["black", "cyan", "green", "magenta"]}, "🧪 التحول الطيني (SWIR B11/B12)", "Clay_SWIR", "20 متر")

    if show_silica:
        l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(aoi).sort("CLOUD_COVER").first().clip(aoi)
        silica_index = l8.select("SR_B6").divide(l8.select("SR_B7")).rename("Silica_Index")
        display_and_download_ee_image(silica_index, {"min": 0.8, "max": 1.8, "palette": ["brown", "white", "purple"]}, "💎 مؤشر السليكا والكوارتز (Landsat SWIR)", "Silica_Index", "30 متر")

    if show_thermal:
        l8_thermal = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(aoi).sort("CLOUD_COVER").first().clip(aoi)
        thermal_band = l8_thermal.select("ST_B10").multiply(0.00341802).add(149.0).rename("Thermal")
        display_and_download_ee_image(thermal_band, {"min": 280, "max": 320, "palette": ["blue", "green", "red"]}, "🌡️ الانبعاث الحراري (Thermal LST)", "Thermal_LST", "30 متر")

    if show_slope:
        dem = ee.Image("JAXA/ALOS/AW3D30/V1_1").select("AVE").clip(aoi)
        slope = ee.Terrain.slope(dem).rename("Slope")
        display_and_download_ee_image(slope, {"min": 0, "max": 45, "palette": ["green", "yellow", "orange", "red"]}, "⛰️ انحدار المجرى (DEM Slope)", "DEM_Slope", "30 متر")

with tab2:
    st.write("### 📊 نافذة المعالجة الحقيقية واستخراج الإحصائيات المكانية (Real GEE Computation)")
    st.markdown("هذه النافذة تقوم بحساب **القيم الإحصائية الفعلية** (متوسط المؤشر، القيم العظمى والصغرى) مباشرة من خوادم Google Earth Engine بناءً على النطاق المحدد.")

    selected_index_type = st.selectbox("اختر المؤشر لحساب إحصائياته الحقيقية:", [
        "نطاق أكسيد الحديد (Iron Oxide)",
        "التحول الطيني (Clay Alteration)",
        "مؤشر السليكا (Silica Index)",
        "الانحدار الطبوغرافي (DEM Slope)"
    ])

    if st.button("🔄 تنفيذ الاستعلام الحقيقي من السحابة"):
        with st.spinner("جاري حساب القيم الفعلية من خوادم GEE..."):
            try:
                # تجهيز الصور للمعالجة الحقيقية
                s2_calc = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(aoi).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).sort("CLOUD_COVER").first().clip(aoi)
                l8_calc = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(aoi).sort("CLOUD_COVER").first().clip(aoi)
                dem_calc = ee.Image("JAXA/ALOS/AW3D30/V1_1").select("AVE").clip(aoi)

                if "أكسيد الحديد" in selected_index_type:
                    img_calc = s2_calc.select("B4").divide(s2_calc.select("B2")).rename("val")
                    scale_val = 10
                elif "التحول الطيني" in selected_index_type:
                    img_calc = s2_calc.select("B11").divide(s2_calc.select("B12")).rename("val")
                    scale_val = 20
                elif "السليكا" in selected_index_type:
                    img_calc = l8_calc.select("SR_B6").divide(l8_calc.select("SR_B7")).rename("val")
                    scale_val = 30
                else:
                    img_calc = ee.Terrain.slope(dem_calc).rename("val")
                    scale_val = 30

                # حساب الإحصائيات الحقيقية باستخدام reduceRegion
                stats = img_calc.reduceRegion(
                    reducer=ee.Reducer.mean().combine(
                        reducer2=ee.Reducer.max(), sharedInputs=True
                    ).combine(
                        reducer2=ee.Reducer.min(), sharedInputs=True
                    ),
                    geometry=aoi,
                    scale=scale_val,
                    maxPixels=1e9
                ).getInfo()

                st.success("✅ تمت عملية المعالجة واستخراج النتائج الحقيقية بنجاح!")
                
                stat_values = list(stats.values()) if stats else []
                mean_val = stat_values[0] if len(stat_values) > 0 and stat_values[0] is not None else 0
                max_val = stat_values[1] if len(stat_values) > 1 and stat_values[1] is not None else 0
                min_val = stat_values[2] if len(stat_values) > 2 and stat_values[2] is not None else 0

                col_res1, col_res2, col_res3 = st.columns(3)
                with col_res1:
                    st.metric(label="📈 المتوسط الحقيقي (Mean)", value=f"{mean_val:.4f}")
                with col_res2:
                    st.metric(label="🔼 القيمة العظمى (Max)", value=f"{max_val:.4f}")
                with col_res3:
                    st.metric(label="🔽 القيمة الصغرى (Min)", value=f"{min_val:.4f}")

                st.info(f"💡 **تحليل هندسي:** تم استخراج هذه القيم بناءً على تحليل عينات حقيقية لمساحة {buffer_km} كم بدقة مكانية تبلغ {scale_val} متر.")

            except Exception as e:
                st.error(f"حدث خطأ أثناء المعالجة السحابية: {str(e)}")
