import os
import zipfile
import tempfile
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.mask import mask
import geopandas as gpd
from shapely.geometry import LineString, box
from sklearn.decomposition import PCA
from skimage.morphology import skeletonize
from skimage.filters import sobel
import matplotlib.pyplot as plt
import streamlit as st

# --- معالجة استدعاء الدالة لضمان التوافق مع Streamlit Cloud ---
try:
    from skimage.feature import meijering
except ImportError:
    try:
        from skimage.filters import meijering
    except ImportError:
        from skimage.filters import frangi as meijering

# إعدادات الصفحة
st.set_page_config(page_title="منظومة كشف القواطع النارية (Dyke Detector)", layout="wide")

st.title("🌋 منظومة كشف القواطع والتراكيب الخطية المدفونة")
st.markdown("قم برفع الحزم الفضائية وتحديد نطاق الإحداثيات لاستخراج التراكيب الخطية وتصديرها بصيغة Shapefile جاهزة لبرامج GIS.")

# --- القائمة الجانبية: إدخال الإحداثيات والملفات ---
st.sidebar.header("📍 1. تحديد نطاق الإحداثيات (AOI)")
use_bbox = st.sidebar.checkbox("تفعيل القص حسب الإحداثيات الجغرافية")

min_lon = st.sidebar.number_input("أقل خط طول (Min Lon)", value=44.00, format="%.4f")
max_lon = st.sidebar.number_input("أعلى خط طول (Max Lon)", value=44.20, format="%.4f")
min_lat = st.sidebar.number_input("أقل خط عرض (Min Lat)", value=14.00, format="%.4f")
max_lat = st.sidebar.number_input("أعلى خط عرض (Max Lat)", value=14.20, format="%.4f")

st.sidebar.header("📁 2. رفع المرئيات الفضائية (TIFF)")
up_swir2 = st.sidebar.file_uploader("حزمة SWIR2 (مثل Band 12)", type=["tif", "tiff"])
up_swir1 = st.sidebar.file_uploader("حزمة SWIR1 (مثل Band 11)", type=["tif", "tiff"])
up_nir = st.sidebar.file_uploader("حزمة NIR (مثل Band 8)", type=["tif", "tiff"])
up_red = st.sidebar.file_uploader("حزمة RED (مثل Band 4)", type=["tif", "tiff"])
up_thermal = st.sidebar.file_uploader("الحزمة الحرارية TIR (اختياري)", type=["tif", "tiff"])
up_sar = st.sidebar.file_uploader("صورة الرادار SAR (اختياري)", type=["tif", "tiff"])
up_dem = st.sidebar.file_uploader("نموذج الارتفاع DEM", type=["tif", "tiff"])

# --- المعالجة التنفيذية ---
if st.button("🚀 بدء المعالجة الطيفية والهيكلية"):
    if not (up_swir2 and up_swir1 and up_nir and up_red and up_dem):
        st.error("يرجى رفع الحزم الأساسية على الأقل: (SWIR2, SWIR1, NIR, RED, DEM)")
    else:
        with st.spinner("جاري معالجة البيانات واستخراج التراكيب الخطية..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                # حفظ الملفات المرفوعة مؤقتاً
                def save_temp(uploaded_file, name):
                    if uploaded_file is None:
                        return None
                    path = os.path.join(tmpdir, name)
                    with open(path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    return path

                swir2_p = save_temp(up_swir2, "swir2.tif")
                swir1_p = save_temp(up_swir1, "swir1.tif")
                nir_p = save_temp(up_nir, "nir.tif")
                red_p = save_temp(up_red, "red.tif")
                thermal_p = save_temp(up_thermal, "thermal.tif")
                sar_p = save_temp(up_sar, "sar.tif")
                dem_p = save_temp(up_dem, "dem.tif")

                # 1. قراءة الحزمة الرئيسية وإعادة الضبط المكاني
                with rasterio.open(swir2_p) as src:
                    crs = src.crs
                    transform = src.transform
                    
                    # القص حسب الإحداثيات إذا تم تفعيلها
                    if use_bbox:
                        bbox_geom = [box(min_lon, min_lat, max_lon, max_lat)]
                        # تحويل الإحداثيات لمطابقة اسقاط الصورة إذا لزم
                        swir2, transform = mask(src, bbox_geom, crop=True)
                        swir2 = swir2[0].astype(np.float32)
                    else:
                        swir2 = src.read(1).astype(np.float32)
                    
                    target_shape = swir2.shape

                def read_and_resample(path):
                    if not path or not os.path.exists(path):
                        return np.zeros(target_shape, dtype=np.float32)
                    with rasterio.open(path) as src:
                        if use_bbox:
                            data, _ = mask(src, [box(min_lon, min_lat, max_lon, max_lat)], crop=True)
                            return data[0].astype(np.float32)
                        return src.read(1, out_shape=target_shape, resampling=Resampling.bilinear).astype(np.float32)

                swir1 = read_and_resample(swir1_p)
                nir = read_and_resample(nir_p)
                red = read_and_resample(red_p)
                thermal = read_and_resample(thermal_p)
                sar = read_and_resample(sar_p)
                dem = read_and_resample(dem_p)

                np.seterr(divide='ignore', invalid='ignore')

                # 2. حساب المؤشرات الطيفية والحرارية
                ferrous_index = np.where(swir1 == 0, 0, swir2 / (swir1 + 1e-5))
                ndvi = np.where((nir + red) == 0, 0, (nir - red) / (nir + red + 1e-5))

                thermal_norm = (thermal - np.nanmin(thermal)) / (np.nanmax(thermal) - np.nanmin(thermal) + 1e-5)
                thermal_edges = sobel(thermal_norm)

                sar_norm = (sar - np.nanmin(sar)) / (np.nanmax(sar) - np.nanmin(sar) + 1e-5)
                sar_edges = sobel(sar_norm)

                # 3. تطبيق PCA
                stacked_bands = np.stack([swir2, swir1, nir, red, thermal_norm], axis=-1)
                h, w, c = stacked_bands.shape
                flat_data = np.nan_to_num(stacked_bands.reshape(-1, c))

                pca = PCA(n_components=2)
                pcs = pca.fit_transform(flat_data)
                pc2_image = pcs[:, 1].reshape(h, w)

                # 4. دمج الطبقات واستخراج الهيكل الخطي
                integrated_feature = (
                    sobel(ferrous_index) * 0.20 + 
                    sobel(ndvi) * 0.10 + 
                    thermal_edges * 0.20 + 
                    sar_edges * 0.15 + 
                    sobel(pc2_image) * 0.20 + 
                    sobel(dem) * 0.15
                )

                ridges = meijering(integrated_feature, sigmas=[1, 2, 3], black_ridges=False)
                binary_lineaments = ridges > np.percentile(ridges, 93)
                skeleton = skeletonize(binary_lineaments)

                # 5. بناء المتجهات وتصحيح الإسناد الجغرافي
                lines = []
                angles = []
                rows, cols = np.where(skeleton)

                for r, c in zip(rows, cols):
                    x1, y1 = rasterio.transform.xy(transform, r, c)
                    x2, y2 = rasterio.transform.xy(transform, r + 1, c + 1)
                    lines.append(LineString([(x1, y1), (x2, y2)]))
                    
                    dx = x2 - x1
                    dy = y2 - y1
                    angle = np.degrees(np.arctan2(dx, dy)) % 360
                    angles.append(angle)

                if lines:
                    gdf = gpd.GeoDataFrame(geometry=lines, crs=crs)
                    gdf = gdf.dissolve()

                    # تصدير ملف GeoJSON
                    geojson_path = os.path.join(tmpdir, "extracted_dykes.geojson")
                    gdf.to_file(geojson_path, driver="GeoJSON")

                    # تصدير Shapefile وضغطه في ملف ZIP ليكون متوافقاً تماماً مع ArcGIS / QGIS
                    shp_dir = os.path.join(tmpdir, "dyke_shapefile")
                    os.makedirs(shp_dir, exist_ok=True)
                    shp_path = os.path.join(shp_dir, "extracted_dykes.shp")
                    gdf.to_file(shp_path, driver="ESRI Shapefile")

                    zip_path = os.path.join(tmpdir, "dyke_shapefile.zip")
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for root, _, files in os.walk(shp_dir):
                            for file in files:
                                zipf.write(os.path.join(root, file), file)

                    st.success("✅ تم كشف القواطع واستخراج التراكيب الخطية بنجاح!")

                    # عرض خيارات التحميل
                    col1, col2 = st.columns(2)
                    with col1:
                        with open(zip_path, "rb") as fp:
                            st.download_button(
                                label="📥 تحميل Shapefile كامل (ZIP لـ GIS)",
                                data=fp,
                                file_name="extracted_dykes_shp.zip",
                                mime="application/zip"
                            )
                    with col2:
                        with open(geojson_path, "rb") as fp:
                            st.download_button(
                                label="📥 تحميل ملف GeoJSON",
                                data=fp,
                                file_name="extracted_dykes.geojson",
                                mime="application/geo+json"
                            )

                    # 6. رسم مخطط الوردة الاتجاهي وعرضه
                    if angles:
                        st.subheader("📊 مخطط الوردة الاتجاهي للتحليل الهيكلي")
                        radii, edges = np.histogram(angles, bins=36, range=(0, 360))
                        theta = np.deg2rad(edges[:-1])
                        
                        fig = plt.figure(figsize=(6, 6))
                        ax = plt.subplot(111, projection='polar')
                        ax.set_theta_zero_location('N')
                        ax.set_theta_direction(-1)
                        ax.bar(theta, radii, width=np.deg2rad(10), bottom=0.0, color='darkred', alpha=0.75, edgecolor='black')
                        plt.title("Lineament Trend Analysis", y=1.1)
                        st.pyplot(fig)
                else:
                    st.warning("لم يتم العثور على خطوط مطابقة في هذه المنطقة.")
