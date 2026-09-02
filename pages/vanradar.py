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

st.title("تحليل واستخراج قنوات الحصى من صور SAR")

uploaded_file = st.file_uploader(
    "قم برفع ملف GeoTIFF الخاص بالرادار", type=["tif", "tiff"]
)

if uploaded_file is not None:
    try:
        # قراءة البيانات الجغرافية
        with rasterio.open(uploaded_file) as src:
            sar_band = src.read(1)
            crs = src.crs
            transform = src.transform
            profile = src.profile.copy()

        # 1. فلترة وتصفية الضوضاء الرادارية
        denoised_band = median_filter(sar_band, size=5)
        valid_pixels = denoised_band[np.isfinite(denoised_band)]

        if len(valid_pixels) > 0:
            p2, p98 = np.percentile(valid_pixels, (2, 98))
            clipped_band = np.clip(denoised_band, p2, p98)
            norm_band = cv2.normalize(
                clipped_band, None, 0, 255, cv2.NORM_MINMAX
            ).astype(np.uint8)

            # 2. العزل والتنعيم الجيومورفولوجي
            _, binary_mask = cv2.threshold(
                norm_band, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )

            # تنظيف النويز الصغير قبل استخراج القنوات
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            cleaned_mask = cv2.morphologyEx(
                binary_mask, cv2.MORPH_OPEN, kernel
            )
            connected_mask = cv2.morphologyEx(
                cleaned_mask, cv2.MORPH_CLOSE, kernel
            )

            # 3. الهيكل العظمي للقنوات
            skeleton = skeletonize(connected_mask > 0).astype(np.uint8) * 255

            # 4. العرض الملون
            colored_sar = cv2.applyColorMap(norm_band, cv2.COLORMAP_VIRIDIS)
            colored_sar_rgb = cv2.cvtColor(colored_sar, cv2.COLOR_BGR2RGB)

            overlay = colored_sar_rgb.copy()
            overlay[skeleton > 0] = [0, 255, 255]

            fig, ax = plt.subplots(1, 2, figsize=(12, 6))
            ax[0].imshow(colored_sar_rgb)
            ax[0].set_title("الرادار الملون (Viridis)")
            ax[0].axis("off")

            ax[1].imshow(overlay)
            ax[1].set_title("شبكة قنوات الحصى المستخرجة")
            ax[1].axis("off")

            st.pyplot(fig)

            st.markdown("---")
            st.subheader("📥 تنزيل النتائج والتصدير الجغرافي")

            col1, col2, col3 = st.columns(3)

            # --- التصدير 1: GeoTIFF مسند للـ GIS ---
            out_profile = profile.copy()
            out_profile.update(dtype=rasterio.uint8, count=1, nodata=0)

            tif_buffer = io.BytesIO()
            with rasterio.MemoryFile() as memfile:
                with memfile.open(**out_profile) as dataset:
                    dataset.write(skeleton, 1)
                tif_buffer.write(memfile.read())

            col1.download_button(
                label="📄 GeoTIFF (GIS/ArcGIS)",
                data=tif_buffer.getvalue(),
                file_name="Gravel_Channels_GeoTIFF.tif",
                mime="image/tiff",
            )

            # --- التصدير 2 & 3: تحويل المصفوفة إلى المتجهات الجغرافية (Vectors) ---
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

                # التأكد من تحويل الإسقاط إلى WGS84 لمتطلبات KML/KMZ و AlpineQuest
                gdf_wgs84 = gdf.to_crs(epsg=4326)

                # تنزيل ملف KML / KMZ لتطبيق AlpineQuest / Google Earth
                kml_buffer = io.BytesIO()
                # حفظ كـ KML مؤقت لتعبئته داخل ملف ZIP/KMZ
                with tempfile.TemporaryDirectory() as tmpdir:
                    kml_path = os.path.join(tmpdir, "channels.kml")
                    gdf_wgs84.to_file(kml_path, driver="KML")

                    kmz_bytes = io.BytesIO()
                    with zipfile.ZipFile(
                        kmz_bytes, "w", zipfile.ZIP_DEFLATED
                    ) as z:
                        z.write(kml_path, arcname="doc.kml")

                    col2.download_button(
                        label="🗺️ KMZ (AlpineQuest)",
                        data=kmz_bytes.getvalue(),
                        file_name="Gravel_Channels_AlpineQuest.kmz",
                        mime="application/vnd.google-earth.kmz",
                    )

                # تنزيل مضغوط Shapefile (.shp) لبرامج GIS
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

                    col3.download_button(
                        label="📦 Shapefile ZIP (GIS)",
                        data=zip_buffer.getvalue(),
                        file_name="Gravel_Channels_Shapefile.zip",
                        mime="application/zip",
                    )
            else:
                st.warning("لم يتم العثور على متجهات جغرافية مستخرجة.")

    except Exception as e:
        st.error(f"حدث خطأ أثناء المعالجة أو التصدير: {e}")
