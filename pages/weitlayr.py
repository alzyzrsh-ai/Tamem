import io
import os
import tempfile
import zipfile
import cv2
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.features import shapes
from scipy.ndimage import median_filter
from shapely.geometry import shape
from skimage.morphology import skeletonize
import streamlit as st

# ضبط إعدادات الصفحة
st.set_page_config(
    page_title="منظومة التحليل الهيدروجيوفيزيائي المدمجة", layout="wide"
)

st.title("🌊 منصة التحليل المدمج واستكشاف قنوات الحصى الجوفية")

st.markdown("""
تُتيح هذه الأداة دمج بيانات الرادار (SAR)، الحرارية (Thermal)، والرطوبة (Moisture) مع عزل التشويش المعدني السطحي لاختيار مواقع الحفر بدقة.
""")

# شريط جانبى لرفع طبقات الاستشعار عن بعد
st.sidebar.header("📁 رفع الطبقات الجغرافية (GeoTIFF)")
radar_file = st.sidebar.file_uploader(
    "1. ملف الرادار (SAR C-Band / L-Band)", type=["tif", "tiff"]
)
thermal_file = st.sidebar.file_uploader(
    "2. الملف الحراري (LST / ATI)", type=["tif", "tiff"]
)
moisture_file = st.sidebar.file_uploader(
    "3. ملف مؤشر الرطوبة (NDMI / SWIR)", type=["tif", "tiff"]
)
mineral_file = st.sidebar.file_uploader(
    "4. قناع المعادن السطحية (اختياري)", type=["tif", "tiff"]
)

if radar_file is not None:
    try:
        # قراءة بيانات الرادار الأساسية
        with rasterio.open(radar_file) as src:
            sar_band = src.read(1)
            crs = src.crs
            transform = src.transform
            profile = src.profile.copy()

        # 1. تصفية ضوضاء الرادار وتنظيف النطاق
        denoised_sar = median_filter(sar_band, size=3)
        valid_pixels = denoised_sar[np.isfinite(denoised_sar)]

        if len(valid_pixels) > 0:
            p2, p98 = np.percentile(valid_pixels, (2, 98))
            clipped_sar = np.clip(denoised_sar, p2, p98)
            norm_sar = cv2.normalize(
                clipped_sar, None, 0, 255, cv2.NORM_MINMAX
            ).astype(np.uint8)

            # 2. تجهيز الطبقات الإضافية في حال رفعها أو محاكاتها
            if thermal_file is not None:
                with rasterio.open(thermal_file) as t_src:
                    thermal_band = t_src.read(1)
            else:
                thermal_band = 255 - norm_sar  # افتراضي

            if moisture_file is not None:
                with rasterio.open(moisture_file) as m_src:
                    moisture_band = m_src.read(1)
            else:
                moisture_band = norm_sar  # افتراضي

            if mineral_file is not None:
                with rasterio.open(mineral_file) as min_src:
                    mineral_mask = min_src.read(1)
            else:
                mineral_mask = np.zeros_like(norm_sar)

            # 3. تطبيع البيانات ودمج المؤشرات الثلاثة (Multi-Criteria Fusion)
            norm_thermal = 1.0 - (
                (thermal_band - np.nanmin(thermal_band))
                / (
                    np.nanmax(thermal_band) - np.nanmin(thermal_band) + 1e-6
                )  # العكس: الأبرد هو الأفضل
            )
            norm_moisture = (moisture_band - np.nanmin(moisture_band)) / (
                np.nanmax(moisture_band) - np.nanmin(moisture_band) + 1e-6
            )
            norm_sar_float = norm_sar / 255.0

            # الوزن الهيدرولوجي: 40% رادار + 35% حرارة + 25% رطوبة
            suitability_index = (
                (norm_sar_float * 0.40)
                + (norm_thermal * 0.35)
                + (norm_moisture * 0.25)
            )

            # استبعاد البصمات المعدنية والسطحية
            suitability_index[mineral_mask > 0] = 0
            suitability_uint8 = (suitability_index * 255).astype(np.uint8)

            # 4. عزل واستخراج القنوات الحصوية (Skeletonization)
            _, binary_channels = cv2.threshold(
                suitability_uint8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            cleaned_binary = cv2.morphologyEx(
                binary_channels, cv2.MORPH_OPEN, kernel
            )

            skeleton = skeletonize(cleaned_binary > 0).astype(np.uint8) * 255

            # 5. التلوين الحراري والعرض الميداني
            colored_sar = cv2.applyColorMap(
                suitability_uint8, cv2.COLORMAP_VIRIDIS
            )
            colored_sar_rgb = cv2.cvtColor(colored_sar, cv2.COLOR_BGR2RGB)

            overlay = colored_sar_rgb.copy()
            overlay[skeleton > 0] = [0, 255, 255]  # لون سيان ساطع للقنوات

            # عرض النتائج في واجهة Streamlit
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("🎯 خريطة الملائمة الهيدرولوجية (Fused Viridis)")
                fig1, ax1 = plt.subplots()
                ax1.imshow(colored_sar_rgb)
                ax1.axis("off")
                st.pyplot(fig1)

            with col2:
                st.subheader("🕸️ شبكة القنوات الحصوية المكتشفة")
                fig2, ax2 = plt.subplots()
                ax2.imshow(overlay)
                ax2.axis("off")
                st.pyplot(fig2)

            st.markdown("---")
            st.subheader("📥 تنزيل وتصدير الخرائط الميدانية")

            d_col1, d_col2, d_col3 = st.columns(3)

            # تصدير GeoTIFF
            out_profile = profile.copy()
            out_profile.update(dtype=rasterio.uint8, count=1, nodata=0)

            tif_buffer = io.BytesIO()
            with rasterio.MemoryFile() as memfile:
                with memfile.open(**out_profile) as dataset:
                    dataset.write(skeleton, 1)
                tif_buffer.write(memfile.read())

            d_col1.download_button(
                label="📄 GeoTIFF (ArcGIS / QGIS)",
                data=tif_buffer.getvalue(),
                file_name="Gravel_Channels_GeoTIFF.tif",
                mime="image/tiff",
            )

            # تحويل المخرجات لمتجهات جغرافية (Vectorization)
            results = (
                {"properties": {"raster_val": v}, "geometry": s}
                for i, (s, v) in enumerate(
                    shapes(skeleton, mask=skeleton > 0, transform=transform)
                )
            )
            geoms = [shape(r["geometry"]) for r in results]

            if len(geoms) > 0:
                gdf = gpd.GeoDataFrame(
                    {"geometry": geoms}, crs=crs if crs else "EPSG:4326"
                )
                gdf_wgs84 = gdf.to_crs(epsg=4326)

                # تصدير KMZ لبرنامج AlpineQuest
                with tempfile.TemporaryDirectory() as tmpdir:
                    kml_path = os.path.join(tmpdir, "doc.kml")
                    gdf_wgs84.to_file(kml_path, driver="KML")

                    kmz_bytes = io.BytesIO()
                    with zipfile.ZipFile(
                        kmz_bytes, "w", zipfile.ZIP_DEFLATED
                    ) as z:
                        z.write(kml_path, arcname="doc.kml")

                    d_col2.download_button(
                        label="🗺️ KMZ (AlpineQuest)",
                        data=kmz_bytes.getvalue(),
                        file_name="Gravel_Channels_AlpineQuest.kmz",
                        mime="application/vnd.google-earth.kmz",
                    )

                # تصدير Shapefile ZIP
                with tempfile.TemporaryDirectory() as tmpdir:
                    shp_path = os.path.join(tmpdir, "gravel_channels.shp")
                    gdf.to_file(shp_path)

                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(
                        zip_buffer, "w", zipfile.ZIP_DEFLATED
                    ) as z:
                        for root, _, files in os.walk(tmpdir):
                            for file in files:
                                z.write(
                                    os.path.join(root, file), arcname=file
                                )

                    d_col3.download_button(
                        label="📦 Shapefile ZIP",
                        data=zip_buffer.getvalue(),
                        file_name="Gravel_Channels_Shapefile.zip",
                        mime="application/zip",
                    )

    except Exception as e:
        st.error(f"حدث خطأ أثناء معالجة الملفات: {e}")

else:
    st.info(
        "👈 يرجى رفع ملف الرادار (GeoTIFF) من القائمة الجانبية للبدء في التحليل."
    )
