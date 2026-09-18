import os
import zipfile
import tempfile
import numpy as np
import geopandas as gpd
from shapely.geometry import LineString
from sklearn.decomposition import PCA
from skimage.morphology import skeletonize
from skimage.filters import sobel
import matplotlib.pyplot as plt
import streamlit as st
import ee

# --- معالجة آمنة لتفعيل سواقات KML بدون AttributeError ---
try:
    import fiona
    fiona.drvsupport.supported_drivers['KML'] = 'rw'
    fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'
except Exception:
    pass

try:
    import geopandas.io.file
    if hasattr(geopandas.io.file, 'fiona'):
        geopandas.io.file.fiona.drvsupport.supported_drivers['KML'] = 'rw'
        geopandas.io.file.fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'
except Exception:
    pass

# --- معالجة استدعاء الدالة لضمان التوافق مع Streamlit Cloud ---
try:
    from skimage.feature import meijering
except ImportError:
    try:
        from skimage.filters import meijering
    except ImportError:
        from skimage.filters import frangi as meijering

# إعدادات الصفحة
st.set_page_config(page_title="منظومة كشف القواطع - التلقائية عبر GEE", layout="wide")

st.title("🌋 منظومة كشف القواطع النارية (سحب واستخراج تلقائي)")
st.markdown("ارفع ملف **KML/KMZ** الخاص بالمنطقة فقط، وسيتم جلب الحزم الفضائية ومعالجتها سحابياً آلياً عبر Google Earth Engine.")

# --- تهيئة Google Earth Engine ---
@st.cache_resource
def init_gee():
    try:
        if "GEE_JSON" in st.secrets:
            import json
            key_dict = json.loads(st.secrets["GEE_JSON"])
            credentials = ee.ServiceAccountCredentials(key_dict['client_email'], key_data=st.secrets["GEE_JSON"])
            ee.Initialize(credentials)
        else:
            ee.Initialize()
        return True
    except Exception as e:
        st.error(f"خطأ في الاتصال بـ Google Earth Engine: {e}")
        return False

gee_ready = init_gee()

# --- القائمة الجانبية ---
st.sidebar.header("🗺️ 1. تحديد نطاق الدراسة (AOI)")
uploaded_kml = st.sidebar.file_uploader("ارفع ملف النطاق (KML أو KMZ)", type=["kml", "kmz"])

st.sidebar.header("⚙️ 2. إعدادات السحب")
cloud_cover = st.sidebar.slider("أقصى نسبة غيوم مقبول (%):", 0, 30, 10)
date_range = st.sidebar.date_input("الفترة الزمنية للالتقاط:", [np.datetime64('2023-01-01'), np.datetime64('2026-01-01')])

# دالة آمنة لقراءة KML/KMZ
def read_kml_safely(file_path):
    try:
        return gpd.read_file(file_path, engine="fiona")
    except Exception:
        return gpd.read_file(file_path)

# --- التنفيذ ---
if st.button("🚀 سحب البيانات ومعالجة القواطع تلقائياً"):
    if not gee_ready:
        st.error("يرجى التأكد من ربط حساب Google Earth Engine.")
    elif not uploaded_kml:
        st.error("يرجى رفع ملف KML أو KMZ المخصص لمنطقة الدراسة.")
    else:
        with st.spinner("جاري سحب الحزم طيفياً وحرارياً وتضاريسياً من Google Earth Engine..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                kml_path = os.path.join(tmpdir, uploaded_kml.name)
                with open(kml_path, "wb") as f:
                    f.write(uploaded_kml.getbuffer())

                if uploaded_kml.name.endswith(".kmz"):
                    with zipfile.ZipFile(kml_path, 'r') as zip_ref:
                        zip_ref.extractall(tmpdir)
                        for file in os.listdir(tmpdir):
                            if file.endswith(".kml"):
                                kml_path = os.path.join(tmpdir, file)
                                break

                aoi_gdf = read_kml_safely(kml_path).to_crs("EPSG:4326")
                bounds = aoi_gdf.total_bounds # [minx, miny, maxx, maxy]
                
                ee_geometry = ee.Geometry.Rectangle([bounds[0], bounds[1], bounds[2], bounds[3]])

                # سحب البيانات سحابياً
                s2_collection = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                                 .filterBounds(ee_geometry)
                                 .filterDate(str(date_range[0]), str(date_range[1]))
                                 .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_cover))
                                 .median()
                                 .clip(ee_geometry))

                dem = ee.Image("COPERNICUS/DEM/GLO30").select('DEM').clip(ee_geometry)

                l8_thermal = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
                              .filterBounds(ee_geometry)
                              .filterDate(str(date_range[0]), str(date_range[1]))
                              .median()
                              .select('ST_B10')
                              .clip(ee_geometry))

                ferrous = s2_collection.select('B12').divide(s2_collection.select('B11').add(0.0001))
                ndvi = s2_collection.normalizedDifference(['B8', 'B4'])

                stacked_ee = ee.Image.cat([
                    s2_collection.select('B12').rename('swir2'),
                    s2_collection.select('B11').rename('swir1'),
                    s2_collection.select('B8').rename('nir'),
                    s2_collection.select('B4').rename('red'),
                    ferrous.rename('ferrous'),
                    ndvi.rename('ndvi'),
                    dem.rename('dem'),
                    l8_thermal.rename('thermal')
                ])

                url = stacked_ee.getDownloadURL({
                    'scale': 30,
                    'crs': 'EPSG:4326',
                    'region': ee_geometry,
                    'format': 'NPY'
                })

                import urllib.request
                npy_path = os.path.join(tmpdir, "data.npy")
                urllib.request.urlretrieve(url, npy_path)
                
                data_dict = np.load(npy_path, allow_pickle=True).item()
                
                swir2 = data_dict['swir2'].astype(np.float32)
                swir1 = data_dict['swir1'].astype(np.float32)
                nir = data_dict['nir'].astype(np.float32)
                red = data_dict['red'].astype(np.float32)
                ferrous_arr = data_dict['ferrous'].astype(np.float32)
                ndvi_arr = data_dict['ndvi'].astype(np.float32)
                dem_arr = data_dict['dem'].astype(np.float32)
                thermal_arr = data_dict['thermal'].astype(np.float32)

                # المعالجة والـ PCA
                np.seterr(divide='ignore', invalid='ignore')
                
                thermal_norm = np.nan_to_num((thermal_arr - np.nanmin(thermal_arr)) / (np.nanmax(thermal_arr) - np.nanmin(thermal_arr) + 1e-5))
                thermal_edges = sobel(thermal_norm)

                stacked_bands = np.stack([swir2, swir1, nir, red, thermal_norm], axis=-1)
                h, w, c = stacked_bands.shape
                flat_data = np.nan_to_num(stacked_bands.reshape(-1, c))

                pca = PCA(n_components=2)
                pcs = pca.fit_transform(flat_data)
                pc2_image = pcs[:, 1].reshape(h, w)

                integrated_feature = (
                    sobel(np.nan_to_num(ferrous_arr)) * 0.25 + 
                    sobel(np.nan_to_num(ndvi_arr)) * 0.15 + 
                    thermal_edges * 0.25 + 
                    sobel(pc2_image) * 0.20 + 
                    sobel(np.nan_to_num(dem_arr)) * 0.15
                )

                ridges = meijering(integrated_feature, sigmas=[1, 2, 3], black_ridges=False)
                binary_lineaments = ridges > np.percentile(ridges, 93)
                skeleton = skeletonize(binary_lineaments)

                # بناء الشبكة الجغرافية
                lines = []
                angles = []
                rows, cols = np.where(skeleton)

                lon_step = (bounds[2] - bounds[0]) / w
                lat_step = (bounds[3] - bounds[1]) / h

                for r, c_idx in zip(rows, cols):
                    x1 = bounds[0] + c_idx * lon_step
                    y1 = bounds[3] - r * lat_step
                    x2 = bounds[0] + (c_idx + 1) * lon_step
                    y2 = bounds[3] - (r + 1) * lat_step
                    
                    lines.append(LineString([(x1, y1), (x2, y2)]))
                    
                    dx = x2 - x1
                    dy = y2 - y1
                    angle = np.degrees(np.arctan2(dx, dy)) % 360
                    angles.append(angle)

                if lines:
                    gdf = gpd.GeoDataFrame(geometry=lines, crs="EPSG:4326")
                    gdf = gdf.dissolve()

                    geojson_path = os.path.join(tmpdir, "extracted_dykes_gee.geojson")
                    gdf.to_file(geojson_path, driver="GeoJSON")

                    shp_dir = os.path.join(tmpdir, "dyke_shapefile_gee")
                    os.makedirs(shp_dir, exist_ok=True)
                    shp_path = os.path.join(shp_dir, "extracted_dykes_gee.shp")
                    gdf.to_file(shp_path, driver="ESRI Shapefile")

                    zip_path = os.path.join(tmpdir, "dyke_shapefile_gee.zip")
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for root, _, files in os.walk(shp_dir):
                            for file in files:
                                zipf.write(os.path.join(root, file), file)

                    st.success("✅ تم جلب البيانات سحابياً واكتشاف التراكيب الخطية بنجاح!")

                    col1, col2 = st.columns(2)
                    with col1:
                        with open(zip_path, "rb") as fp:
                            st.download_button(
                                label="📥 تحميل Shapefile كامل (ZIP لـ GIS)",
                                data=fp,
                                file_name="dykes_GEE_auto.zip",
                                mime="application/zip"
                            )
                    with col2:
                        with open(geojson_path, "rb") as fp:
                            st.download_button(
                                label="📥 تحميل ملف GeoJSON",
                                data=fp,
                                file_name="dykes_GEE_auto.geojson",
                                mime="application/geo+json"
                            )

                    if angles:
                        st.subheader("📊 مخطط الوردة الاتجاهي للنطاق المجلوب")
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
                    st.warning("لم يتم العثور على خطوط مطابقة داخل النطاق المرفوع.")
