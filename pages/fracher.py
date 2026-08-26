import io
import zipfile
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.io import MemoryFile
from shapely.geometry import shape
from shapely.ops import linemerge
from skimage.morphology import remove_small_objects, skeletonize
import streamlit as st

st.set_page_config(
    page_title="استخراج خطوط الصدوع", page_icon="🗺️", layout="wide"
)

st.title("🗺️ أداة استخراج وحساب الصدوع والكسور الجيولوجية")
st.write(
    "قم برفع ملف الراستر الثنائي (TIFF) لمعالجته وتحويله إلى شبكة متجهة (Shapefile / GeoJSON)."
)

# --- 1. رفع الملف عبر الواجهة ---
uploaded_file = st.file_uploader(
    "ارفع ملف راستر الصدوع (TIFF / TIF)", type=["tif", "tiff"]
)

# شريط إعدادات تصفية الضوضاء
min_noise_size = st.sidebar.slider(
    "حد تصفية الضوضاء (أقل حجم للبكسلات):",
    min_value=1,
    max_value=100,
    value=15,
)

if uploaded_file is not None:
    try:
        # --- 2. قراءة الملف بأمان عبر MemoryFile ---
        file_bytes = uploaded_file.read()

        with MemoryFile(file_bytes) as memfile:
            with memfile.open() as src:
                img = src.read(1)
                transform = src.transform
                crs = src.crs

        st.success("تم رفع وقراءة ملف الراستر بنجاح!")

        if st.button("بدء معالجة واستخلاص الصدوع 🚀"):
            with st.spinner(
                "جاري تنظيف الضوضاء واستخلاص الهيكل المحوري..."
            ):
                # --- 3. تنظيف الضوضاء والتنحيف ---
                binary_mask = img > 0
                cleaned_mask = remove_small_objects(
                    binary_mask, min_size=min_noise_size
                )
                skeleton = skeletonize(cleaned_mask).astype(np.uint8)

                # --- 4. التحويل إلى خطوط متجهة ---
                results = (
                    {"properties": {"raster_val": v}, "geometry": s}
                    for i, (s, v) in enumerate(
                        shapes(skeleton, mask=skeleton, transform=transform)
                    )
                )

                geoms = list(results)
                polygons = [shape(g["geometry"]) for g in geoms]

                lines = []
                for poly in polygons:
                    line = poly.boundary
                    if line.geom_type == "LineString":
                        lines.append(line)
                    elif line.geom_type == "MultiLineString":
                        lines.extend(list(line.geoms))

                if lines:
                    merged_lines = linemerge(lines)
                    final_lines = (
                        [merged_lines]
                        if merged_lines.geom_type == "LineString"
                        else list(merged_lines.geoms)
                    )

                    # --- 5. بناء GeoDataFrame وتصحيح الإسقاط ---
                    gdf = gpd.GeoDataFrame(geometry=final_lines, crs=crs)
                    gdf["Length_m"] = gdf.length

                    # تحضير GeoJSON للتحميل
                    if crs is not None:
                        gdf_wgs84 = gdf.to_crs(epsg=4326)
                        geojson_bytes = gdf_wgs84.to_json()
                    else:
                        geojson_bytes = gdf.to_json()

                    # تحضير Shapefile مضغوط (ZIP) للتحميل
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(
                        zip_buffer, "w", zipfile.ZIP_DEFLATED
                    ) as zip_file:
                        # إنشاء مجلد مؤقت داخل الذاكرة لحفظ عناصر الشيب فايل
                        import tempfile

                        with tempfile.TemporaryDirectory() as tmpdir:
                            tmp_shp = f"{tmpdir}/Extracted_Faults.shp"
                            gdf.to_file(tmp_shp)
                            for ext in [
                                ".shp",
                                ".shx",
                                ".dbf",
                                ".prj",
                                ".cpg",
                            ]:
                                file_path = f"{tmpdir}/Extracted_Faults{ext}"
                                if zipfile.os.path.exists(file_path):
                                    zip_file.write(
                                        file_path,
                                        arcname=f"Extracted_Faults{ext}",
                                    )

                    st.subheader("📊 النتائج والإحصائيات:")
                    st.write(f"عدد الصدوع المستخرجة: **{len(gdf)}**")
                    st.write(
                        f"إجمالي أطوال الصدوع: **{gdf['Length_m'].sum():,.2f} متر**"
                    )

                    col1, col2 = st.columns(2)
                    with col1:
                        st.download_button(
                            label="📥 تحميل GeoJSON (Google Earth/Engine)",
                            data=geojson_bytes,
                            file_name="Extracted_Faults_WGS84.geojson",
                            mime="application/json",
                        )
                    with col2:
                        st.download_button(
                            label="📥 تحميل Shapefile (ArcGIS/QGIS - ZIP)",
                            data=zip_buffer.getvalue(),
                            file_name="Extracted_Faults_Shapefile.zip",
                            mime="application/zip",
                        )
                else:
                    st.warning(
                        "لم يتم العثور على أجزاء خطية بعد التصفية. جرب تقليل حد تصفية الضوضاء."
                    )

    except Exception as e:
        st.error(f"حدث خطأ أثناء معالجة الملف: {str(e)}")
else:
    st.info("يرجى رفع ملف TIFF للبدء.")
