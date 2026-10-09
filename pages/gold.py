import json
import ee
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.raster_layers import ImageOverlay

# 1. إعداد واجهة الصفحة
st.set_page_config(
    page_title="المنصة الفضائية المتقدمة لمعالجة الشذوذات المعدنية والهيدرولوجية",
    page_icon="🛰️",
    layout="wide",
)

st.title("🛰️ المنصة الفضائية المتقدمة لمعالجة الشذوذات المعدنية والهيدرولوجية")
st.markdown("نظام معالجة سحابي متكامل لإسقاط الشذوذات على صور الواقع وتصدير الإحداثيات الميدانية.")

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
# استخراج حدود الإحداثيات لطبقة الإسقاط (Bounds for Folium Overlay)
min_lon, min_lat, max_lon, max_lat = target_lon - delta, target_lat - delta, target_lon + delta, target_lat + delta

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
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🗺️ الإسقاط الجوي والشفافية الميدانية",
    "📍 أداة استخراج الإحداثيات والـ Waypoints",
    "🛰️ العرض والتحميل الفضائي", 
    "⚙️ نموذج الاحتمالية المرجح (WPI Engine)", 
    "📍 استخراج وتصدير المتجهات (KML)"
])

with tab1:
    st.write("### 🗺️ خريطة الإسقاط والشفافية (إسقاط الشذوذ على صور الواقع عالي الدقة)")
    st.markdown("تتيح لك هذه الخريطة استعراض صورة الأقمار الصناعية الحقيقية للواقع مع إسقاط خريطة الاحتمالية كطبقة شفافة (`Overlay`) لتحديد أماكن العروق بدقة متناهية.")

    opacity_val = st.slider("درجة شفافية طبقة الشذوذ فوق الواقع:", 0.0, 1.0, 0.6, 0.05)

    try:
        # حساب خريطة الاحتمالية (WPI) لتوليد رابط الصورة الاسقاطية
        l8_map = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(aoi).sort("CLOUD_COVER").first().clip(aoi)
        s2_map = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(aoi).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).sort("CLOUD_COVER").first().clip(aoi)
        dem_map = ee.Image("JAXA/ALOS/AW3D30/V1_1").select("AVE").clip(aoi)

        silica_n = l8_map.select("SR_B6").divide(l8_map.select("SR_B7")).unitScale(0.8, 2.0)
        iron_n = s2_map.select("B4").divide(s2_map.select("B2")).unitScale(0.9, 2.2)
        clay_n = s2_map.select("B11").divide(s2_map.select("B12")).unitScale(0.9, 2.0)
        slope_n = ee.Terrain.slope(dem_map).unitScale(0, 45)

        wpi_map_layer = silica_n.multiply(0.4).add(iron_n.multiply(0.3)).add(clay_n.multiply(0.2)).add(slope_n.multiply(0.1)).rename("WPI")
        
        wpi_overlay_url = wpi_map_layer.getThumbURL({
            "region": region,
            "dimensions": "800x800",
            "format": "jpg",
            "min": 0.1,
            "max": 0.8,
            "palette": ["blue", "green", "yellow", "orange", "red"]
        })

        # بناء خريطة التفاعل (Folium)
        m_real = folium.Map(location=[target_lat, target_lon], zoom_start=13, tiles=None)

        # إضافة خلفية الأقمار الصناعية للواقع (Esri Satellite)
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri Satellite',
            name='Esri Satellite',
            overlay=False,
            control=True
        ).add_to(m_real)

        # دمج طبقة الشذوذ فوق الواقع بشفافية قابلة للتحكم
        ImageOverlay(
            image=wpi_overlay_url,
            bounds=[[min_lat, min_lon], [max_lat, max_lon]],
            opacity=opacity_val,
            name="طبقة الشذوذ الجيولوجي (WPI)"
        ).add_to(m_real)

        folium.Marker(
            [target_lat, target_lon],
            popup=f"مركز الدراسة الرئيسي<br>Lat: {target_lat}, Lon: {target_lon}",
            icon=folium.Icon(color="red", icon="info-sign")
        ).add_to(m_real)

        folium.LayerControl().add_to(m_real)

        # عرض الخريطة التفاعلية مع دعم النقر لاستخراج الإحداثيات
        map_interaction = st_folium(m_real, width=800, height=550)

        if map_interaction and map_interaction.get("last_clicked"):
            c_lat = map_interaction["last_clicked"]["lat"]
            c_lon = map_interaction["last_clicked"]["lng"]
            st.success(mrow_msg := f"📍 **الإحداثية المحددة من خريطة الواقع:** Lat: {c_lat:.6f}, Lon: {c_lon:.6f}")
            st.info("💡 يمكنك أخذ هذه الإحداثيات ونقلها للتاب التالي لتوليد ملف التوجيه KML.")

    except Exception as e:
        st.warning(f"جاري تحميل خريطة الإسقاط الميداني... (تأكد من اتصال GEE): {str(e)}")

with tab2:
    st.write("### 📍 أداة تحديد وتحويل إحداثيات الأهداف الميدانية")
    st.markdown("إذا استخرجت إحداثيات أي نقطة ملفتة للانتباه من خريطة الواقع أو الشذوذ، أدخلها هنا لتحويلها فوراً إلى نقطة توجيه (Waypoint) وتصديرها لتطبيق الـ AlpineQuest.")

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

            pt_kml_url = fc.getDownloadURL('kml')

            st.success("✅ تم توليد نقطة التوجيه بنجاح!")
            st.code(f"الإحداثيات المعتمدة:\nLat: {target_point_lat:.6f}\nLon: {target_point_lon:.6f}")
            st.markdown(f"📥 **[انقر هنا لتحميل ملف الـ KML الخاص بهذه النقطة لـ AlpineQuest]({pt_kml_url})**")
            st.info("💡 افتح هذا الملف مباشرة في هاتفك عبر تطبيق **AlpineQuest** أو **Google Earth** للتوجه المباشر نحو الإحداثية في الحقل.")

        except Exception as e:
            st.error(f"حدث خطأ أثناء توليد نقطة الإحداثيات: {str(e)}")

with tab3:
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
        s2_clay = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(aoi).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).sort("CLOUD_COVER").first().clip(aoi)
        clay_ratio = s2_clay.select("B11").divide(s2_clay.select("B12")).rename("Clay_Alteration")
        display_and_download_ee_image(clay_ratio, {"min": 0.9, "max": 2.2, "palette": ["black", "cyan", "green", "magenta"]}, "🧪 التحول الطيني (SWIR B11/B12 - مقياس متدرج)", "Clay_SWIR", "20 متر")

    if show_silica:
        l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(aoi).sort("CLOUD_COVER").first().clip(aoi)
        silica_index = l8.select("SR_B6").divide(l8.select("SR_B7")).rename("Silica_Index")
        display_and_download_ee_image(silica_index, {"min": 0.7, "max": 2.0, "palette": ["brown", "white", "purple"]}, "💎 مؤشر السليكا والكوارتز (Landsat SWIR - عروق المرو)", "Silica_Index", "30 متر")

    if show_thermal:
        l8_thermal = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(aoi).sort("CLOUD_COVER").first().clip(aoi)
        thermal_band = l8_thermal.select("ST_B10").multiply(0.00341802).add(149.0).rename("Thermal")
        display_and_download_ee_image(thermal_band, {"min": 275, "max": 325, "palette": ["blue", "green", "red"]}, "🌡️ الانبعاث الحراري (Thermal LST)", "Thermal_LST", "30 متر")

    if show_slope:
        dem = ee.Image("JAXA/ALOS/AW3D30/V1_1").select("AVE").clip(aoi)
        slope = ee.Terrain.slope(dem).rename("Slope")
        display_and_download_ee_image(slope, {"min": 0, "max": 50, "palette": ["green", "yellow", "orange", "red"]}, "⛰️ انحدار المجرى ومصايد الذهب (DEM Slope)", "DEM_Slope", "30 متر")

with tab4:
    st.write("### ⚙️ محرك الاحتمالية المرجح لاستنباط عروق الذهب والمرو (WPI Engine)")
    st.markdown("هذا المحرك يدمج المعطيات بنظام أوزان احصائية متدرجة لتظهر خريطة الاحتمالات بوضوح تام بدون أي شاشة سوداء.")

    col_w1, col_w2 = st.columns(2)
    with col_w1:
        w_silica = st.slider("وزن مؤشر السليكا (عروق المرو):", 0.0, 1.0, 0.4, 0.05)
        w_iron = st.slider("وزن نطاق أكسيد الحديد:", 0.0, 1.0, 0.3, 0.05)
    with col_w2:
        w_clay = st.slider("وزن التحول الطيني:", 0.0, 1.0, 0.2, 0.05)
        w_slope = st.slider("وزن الانحدار الطبوغرافي:", 0.0, 1.0, 0.1, 0.05)

    if st.button("🚀 حساب خريطة الاحتمالية الاستكشافية (WPI)"):
        with st.spinner("جاري معالجة ونمذجة المؤشرات الطيفية والطبوغرافية..."):
            try:
                l8_m = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(aoi).sort("CLOUD_COVER").first().clip(aoi)
                s2_m = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(aoi).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).sort("CLOUD_COVER").first().clip(aoi)
                dem_m = ee.Image("JAXA/ALOS/AW3D30/V1_1").select("AVE").clip(aoi)

                silica_n = l8_m.select("SR_B6").divide(l8_m.select("SR_B7")).unitScale(0.8, 2.0)
                iron_n = s2_m.select("B4").divide(s2_m.select("B2")).unitScale(0.9, 2.2)
                clay_n = s2_m.select("B11").divide(s2_m.select("B12")).unitScale(0.9, 2.0)
                slope_n = ee.Terrain.slope(dem_m).unitScale(0, 45)

                wpi_map = silica_n.multiply(w_silica) \
                    .add(iron_n.multiply(w_iron)) \
                    .add(clay_n.multiply(w_clay)) \
                    .add(slope_n.multiply(w_slope)) \
                    .rename("WPI_Target")

                wpi_thumb = wpi_map.getThumbURL({
                    "region": region,
                    "dimensions": "800x800",
                    "format": "jpg",
                    "min": 0.1,
                    "max": 0.8,
                    "palette": ["blue", "green", "yellow", "orange", "red"]
                })

                st.success("✅ تم حساب خريطة الاحتمالية الاستكشافية بنجاح!")
                st.subheader("🎯 خريطة الاحتمال المرجح لعروق المرو والذهب")
                st.image(wpi_thumb, use_container_width=True, caption="🧭 اتجاه الشمال نحو الأعلى | الألوان من الأزرق (أقل احتمالاً) إلى الأحمر (أعلى احتمالية للهدف)")

                wpi_download = wpi_map.getDownloadURL({
                    "name": "Gold_Prospectivity_WPI_Map",
                    "region": aoi,
                    "scale": 15,
                    "format": "GEO_TIFF"
                })
                st.markdown(f"📥 [تحميل خريطة الاحتمالية بصيغة GeoTIFF للـ GIS]({wpi_download})")

            except Exception as e:
                st.error(f"حدث خطأ أثناء تنفيذ نموذج الاحتمالية: {str(e)}")

with tab5:
    st.write("### 📍 التصدير الميداني المتجه (KML لـ Google Earth & AlpineQuest)")
    st.markdown("تحويل الشذوذ الطيفي لعروق المرو أو خطوط الهدف إلى مضلعات هندسية داخل الإطار المربع جاهزة للاستخدام الحقلي.")

    vector_target = st.selectbox("اختر الطبقة المراد تحويلها إلى متجهات:", [
        "مؤشر السليكا وعروق الكوارتز (Landsat SWIR)",
        "نطاق أكسيد الحديد (Iron Oxide)",
        "التحول الطيني (Clay Alteration)"
    ])

    threshold_val = st.slider("عتبة فصل الشذوذ (Threshold من الأدنى للأعلى):", 0.8, 2.5, 1.2, 0.05)

    if st.button("🗺️ استخراج المتجهات وتوليد ملف KML الميداني"):
        with st.spinner("جاري تحويل الشذوذات إلى مضلعات وخطوط متجهة (Vectors)..."):
            try:
                l8_v = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(aoi).sort("CLOUD_COVER").first().clip(aoi)
                s2_v = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(aoi).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).sort("CLOUD_COVER").first().clip(aoi)
                
                if "السليكا" in vector_target:
                    raw_img = l8_v.select("SR_B6").divide(l8_v.select("SR_B7"))
                    scale_v = 30
                elif "أكسيد الحديد" in vector_target:
                    raw_img = s2_v.select("B4").divide(s2_v.select("B2"))
                    scale_v = 10
                else:
                    raw_img = s2_v.select("B11").divide(s2_v.select("B12"))
                    scale_v = 20

                mask = raw_img.gt(threshold_val)

                vectors = mask.selfMask().reduceToVectors(
                    geometry=aoi,
                    scale=scale_v,
                    geometryType='polygon',
                    eightConnected=True,
                    maxPixels=1e9
                )

                kml_url = vectors.getDownloadURL('kml')

                st.success("✅ تم استخراج معالم الهدف المتجهة بنجاح!")
                st.markdown(f"📥 **[انقر هنا لتحميل ملف الـ KML الميداني]({kml_url})**")
                st.info("💡 **طريقة الاستخدام:** قم بتحميل الملف، ثم فتحه مباشرة في تطبيق **AlpineQuest** على هاتفك المحمول أو إفلاته في **Google Earth** لرؤية امتداد العروق والشذوذات مرسومة بدقة في الموقع الحقيقي.")

            except Exception as e:
                st.error(f"حدث خطأ أثناء استخراج المتجهات: {str(e)}")
