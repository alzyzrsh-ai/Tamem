import io
import tempfile
import zipfile
import geopandas as gpd
import matplotlib.pyplot as plt
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

# تهيئة Session State
if "processed" not in st.session_state:
    st.session_state.processed = False
if "geojson_bytes" not in st.session_state:
    st.session_state.geojson_bytes = None
if "zip_bytes" not in st.session_state:
    st.session_state.zip_bytes = None
if "stats" not in st.session_state:
    st.session_state.stats = {}
if "orig_img" not in st.session_state:
    st.session_state.orig_img = None
if "skel_img" not in st.session_state:
    st.session_state.skel_img = None

uploaded_file = st.file_uploader(
    "ارفع ملف راستر الصدوع (TIFF / TIF)", type=["tif", "tiff"]
)
min_noise_size = st.sidebar.slider(
    "حد تصفية الضوضاء (أقل حجم للبكسلات):", 1, 100, 15
)

if uploaded_file is not None:
    # قراءة الصورة وعرض المعاينة الأولية
    file_bytes = uploaded_file.read()
    with MemoryFile(file_bytes) as memfile:
        with memfile.open() as src:
            img = src.read(1)
            transform = src.transform
            crs = src.crs

    st.success("تم رفع وقراءة ملف الراستر بنجاح!")

    # عرض معاينة الراستر المرفوع فوراً
    st.subheader("🖼️ معاينة راستر المدخلات:")
    st.image(
        img > 0,
        caption="راستر الصدوع الأصلي (Binary)",
        use_container_width=True,
        clamp=True,
    )

    if st.button("بدء معالجة واستخلاص الصدوع 🚀"):
        try:
            with st.spinner("جاري المعالجة والتنظيف وإعداد الخرائط..."):
                # 1. المعالجة والتنظيف
                binary_mask = img > 0
                cleaned_mask = remove_small_objects(
                    binary_mask, min_size=min_noise_size
                )
                skeleton = skeletonize(cleaned_mask).astype(np.uint8)

                # 2. تحويل إلى Vector
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

                    gdf = gpd.GeoDataFrame(geometry=final_lines, crs=crs)
                    gdf["Length_m"] = gdf.length

                    # 3. حفظ GeoJSON
                    if crs is not None:
                        gdf_wgs84 = gdf.to_crs(epsg=4326)
                        st.session_state.geojson_bytes = (
                            gdf_wgs84.to_json().encode("utf-8")
                        )
                    else:
                        st.session_state.geojson_bytes = gdf.to_json().encode(
                            "utf-8"
                        )

                    # 4. حفظ Shapefile ZIP
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(
                        zip_buffer, "w", zipfile.ZIP_DEFLATED
                    ) as zip_file:
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

                    st.session_state.zip_bytes = zip_buffer.getvalue()
                    st.session_state.stats = {
                        "count": len(gdf),
                        "length": gdf["Length_m"].sum(),
                    }
                    st.session_state.skel_img = skeleton
                    st.session_state.processed = True
                else:
                    st.warning(
                        "لم يتم استخراج أية خطوط، حاول تقليل حد تصفية الضوضاء."
                    )

        except Exception as e:
            st.error(f"حدث خطأ أثناء المعالجة: {str(e)}")

    # عرض الخرائط والنتائج بعد المعالجة
    if st.session_state.processed:
        st.subheader("🗺️ صورة الصدوع بعد التنظيف والتنحيف (Skeleton):")
        st.image(
            st.session_state.skel_img,
            caption="شبكة الصدوع المستخرجة (بكسل واحد)",
            use_container_width=True,
            clamp=True,
        )

        st.success("تم استخراج الصدوع بنجاح!")
        st.subheader("📊 النتائج الإحصائية:")
        st.write(
            f"عدد الصدوع المستخرجة: **{st.session_state.stats['count']}**"
        )
        st.write(
            f"إجمالي الأطوال: **{st.session_state.stats['length']:,.2f} متر**"
        )

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📥 تحميل GeoJSON",
                data=st.session_state.geojson_bytes,
                file_name="Extracted_Faults_WGS84.geojson",
                mime="application/json",
            )
        with col2:
            st.download_button(
                label="📥 تحميل Shapefile (ZIP)",
                data=st.session_state.zip_bytes,
                file_name="Extracted_Faults_Shapefile.zip",
                mime="application/zip",
            )
