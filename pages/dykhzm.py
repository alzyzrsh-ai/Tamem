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

import os
import zipfile
import tempfile
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.enums import Resampling
from rasterio.mask import mask
from shapely.geometry import LineString, box
from sklearn.decomposition import PCA
from skimage.morphology import skeletonize
from skimage.filters import sobel
import matplotlib.pyplot as plt
import streamlit as st

# مكتبات الجلب التلقائي السحابي
import pystac_client
import planetary_computer

# --- معالجة آمنة لدعم KML / WPT ---
try:
    import fiona
    fiona.drvsupport.supported_drivers['KML'] = 'rw'
    fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'
except Exception:
    pass

try:
    from skimage.feature import meijering
except ImportError:
    try:
        from skimage.filters import meijering
    except ImportError:
        from skimage.filters import frangi as meijering

st.set_page_config(page_title="منظومة كشف القواطع - التلقائية بالكامل", layout="wide")

st.title("🌋 منظومة كشف القواطع النارية (سحب واستخراج تلقائي)")
st.info("💡 ارفع ملف المنطقة (AlpineQuest / KML / KMZ) فقط، وسيتم جلب الحزم الفضائية ومعالجتها سحابياً آلياً.")

# --- القائمة الجانبية ---
st.sidebar.header("🗺️ 1. رفع ملف المنطقة")
uploaded_aoi = st.sidebar.file_uploader("ارفع ملف النطاق (AlpineQuest KML / KMZ / WPT)", type=["kml", "kmz", "wpt", "ldk"])

st.sidebar.header("⚙️ 2. خيارات السحب")
date_range = st.sidebar.date_input("الفترة الزمنية للمرئيات:", [np.datetime64('2023-01-01'), np.datetime64('2026-01-01')])
max_cloud = st.sidebar.slider("أقصى نسبة غيوم مقبول (%):", 0, 20, 10)

def load_aoi_file(file_bytes, file_name, tmpdir):
    file_path = os.path.join(tmpdir, file_name)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    if file_name.lower().endswith(".kmz"):
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)
                for f_in_zip in os.listdir(tmpdir):
                    if f_in_zip.lower().endswith(".kml"):
                        file_path = os.path.join(tmpdir, f_in_zip)
                        break
        except Exception:
            pass

    try:
        return gpd.read_file(file_path, engine="fiona")
    except Exception:
        return gpd.read_file(file_path)

# --- التنفيذ التلقائي ---
if st.button("🚀 جلب الحزم تلقائياً واستخراج القواطع"):
    if not uploaded_aoi:
        st.error("يرجى رفع ملف نطاق المنطقة من القائمة الجانبية أولاً.")
    else:
        with st.spinner("جاري قراءة الملف وسحب الحزم الفضائية (Sentinel-2) سحابياً..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                # 1. قراءة حدود المنطقة
                aoi_gdf = load_aoi_file(uploaded_aoi.getbuffer(), uploaded_aoi.name, tmpdir).to_crs("EPSG:4326")
                bounds = list(aoi_gdf.total_bounds) # [minx, miny, maxx, maxy]

                # 2. البحث عن مرئيات Sentinel-2 سحابياً عبر STAC
                catalog = pystac_client.Client.open(
                    "https://planetarycomputer.microsoft.com/api/stac/v1",
                    modifier=planetary_computer.sign_inplace,
                )

                search = catalog.search(
                    collections=["sentinel-2-l2a"],
                    bbox=bounds,
                    datetime=f"{date_range[0]}/{date_range[1]}",
                    query={"eo:cloud_cover": {"lt": max_cloud}},
                )

                items = list(search.items())
                if not items:
                    st.error("لم يتم العثور على مرئيات فضائية خالية من الغيوم لهذه المنطقة في هذه الفترة.")
                else:
                    item = items[0] # اختيار أفضل مرئية
                    
                    # 3. فتح الحزم مباشرة عبر روابط الشبكة وقصها
                    crop_shape = [aoi_gdf.geometry.iloc[0]] if aoi_gdf.geometry.iloc[0].geom_type in ['Polygon', 'MultiPolygon'] else [aoi_gdf.unary_union.convex_hull]

                    def fetch_band(asset_key):
                        href = item.assets[asset_key].href
                        with rasterio.open(href) as src:
                            # إعادة إسقاط مضلع القص ليتوافق مع مرئية Sentinel
                            aoi_reprojected = aoi_gdf.to_crs(src.crs)
                            geom = [aoi_reprojected.geometry.iloc[0]] if aoi_reprojected.geometry.iloc[0].geom_type in ['Polygon', 'MultiPolygon'] else [aoi_reprojected.unary_union.convex_hull]
                            data, out_transform = mask(src, geom, crop=True)
                            return data[0].astype(np.float32), out_transform, src.crs

                    swir2, transform, raster_crs = fetch_band("B12")
                    swir1, _, _ = fetch_band("B11")
                    nir, _, _ = fetch_band("B08")
                    red, _, _ = fetch_band("B04")

                    np.seterr(divide='ignore', invalid='ignore')

                    # 4. المعالجة والتحليل الطيفي (PCA & Lineament Extraction)
                    ferrous_index = np.where(swir1 == 0, 0, swir2 / (swir1 + 1e-5))
                    ndvi = np.where((nir + red) == 0, 0, (nir - red) / (nir + red + 1e-5))

                    stacked_bands = np.stack([swir2, swir1, nir, red], axis=-1)
                    h, w, c = stacked_bands.shape
                    flat_data = np.nan_to_num(stacked_bands.reshape(-1, c))

                    pca = PCA(n_components=2)
                    pcs = pca.fit_transform(flat_data)
                    pc2_image = pcs[:, 1].reshape(h, w)

                    integrated_feature = (
                        sobel(ferrous_index) * 0.40 + 
                        sobel(ndvi) * 0.20 + 
                        sobel(pc2_image) * 0.40
                    )

                    ridges = meijering(integrated_feature, sigmas=[1, 2, 3], black_ridges=False)
                    binary_lineaments = ridges > np.percentile(ridges, 93)
                    skeleton = skeletonize(binary_lineaments)

                    # 5. تصدير النتائج متجهة
                    lines = []
                    angles = []
                    rows, cols = np.where(skeleton)

                    for r, c_idx in zip(rows, cols):
                        x1, y1 = rasterio.transform.xy(transform, r, c_idx)
                        x2, y2 = rasterio.transform.xy(transform, r + 1, c_idx + 1)
                        lines.append(LineString([(x1, y1), (x2, y2)]))
                        
                        dx = x2 - x1
                        dy = y2 - y1
                        angle = np.degrees(np.arctan2(dx, dy)) % 360
                        angles.append(angle)

                    if lines:
                        gdf = gpd.GeoDataFrame(geometry=lines, crs=raster_crs)
                        gdf = gdf.dissolve()

                        zip_path = os.path.join(tmpdir, "dykes_auto.zip")
                        shp_dir = os.path.join(tmpdir, "shp")
                        os.makedirs(shp_dir, exist_ok=True)
                        gdf.to_file(os.path.join(shp_dir, "dykes.shp"), driver="ESRI Shapefile")

                        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                            for root, _, files in os.walk(shp_dir):
                                for file in files:
                                    zipf.write(os.path.join(root, file), file)

                        st.success("✅ تم سحب الحزم سحابياً واكتشاف التراكيب الخطية بنجاح!")

                        with open(zip_path, "rb") as fp:
                            st.download_button(
                                label="📥 تحميل Shapefile المكتشف (ZIP)",
                                data=fp,
                                file_name="extracted_dykes.zip",
                                mime="application/zip"
                            )

                        if angles:
                            st.subheader("📊 مخطط الوردة الاتجاهي")
                            radii, edges = np.histogram(angles, bins=36, range=(0, 360))
                            theta = np.deg2rad(edges[:-1])
                            
                            fig = plt.figure(figsize=(6, 6))
                            ax = plt.subplot(111, projection='polar')
                            ax.set_theta_zero_location('N')
                            ax.set_theta_direction(-1)
                            ax.bar(theta, radii, width=np.deg2rad(10), bottom=0.0, color='darkred', alpha=0.75, edgecolor='black')
                            plt.title("Lineament Trend Analysis", y=1.1)
                            st.pyplot(fig)

