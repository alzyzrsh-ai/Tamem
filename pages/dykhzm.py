import os
import re
import zipfile
import tempfile
from datetime import date
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from shapely.geometry import LineString, Point, Polygon
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
st.info("💡 ارفع ملف المنطقة (AlpineQuest / KML / KMZ / WPT) فقط، وسيتم جلب الحزم الفضائية ومعالجتها سحابياً آلياً.")

# --- القائمة الجانبية ---
st.sidebar.header("🗺️ 1. رفع ملف المنطقة")
uploaded_aoi = st.sidebar.file_uploader("ارفع ملف النطاق (AlpineQuest KML / KMZ / WPT)", type=["kml", "kmz", "wpt", "ldk"])

st.sidebar.header("⚙️ 2. خيارات السحب")
date_range = st.sidebar.date_input("الفترة الزمنية للمرئيات:", [date(2023, 1, 1), date(2026, 1, 1)])
max_cloud = st.sidebar.slider("أقصى نسبة غيوم مقبول (%):", 0, 20, 10)

# --- دالة شاملة لقراءة جميع أنواع ملفات AlpineQuest و KML ---
def load_aoi_file(file_bytes, file_name, tmpdir):
    file_path = os.path.join(tmpdir, file_name)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # 1. فتح ملفات KMZ المضغوطة
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

    # 2. القراءة القياسية عبر GeoPandas
    try:
        return gpd.read_file(file_path, engine="fiona")
    except Exception:
        try:
            return gpd.read_file(file_path)
        except Exception:
            pass

    # 3. معالج خاص لملفات AlpineQuest الثنائية (.wpt / .ldk)
    coords = []
    try:
        content = file_bytes.decode('latin-1', errors='ignore')
        matches = re.findall(r'([-+]?\d{1,2}\.\d{4,8})[\s,]+([-+]?\d{1,3}\.\d{4,8})', content)
        for lat, lon in matches:
            lat_f, lon_f = float(lat), float(lon)
            if -90 <= lat_f <= 90 and -180 <= lon_f <= 180:
                coords.append((lon_f, lat_f))
    except Exception:
        pass

    if len(coords) >= 3:
        poly = Polygon(coords)
        return gpd.GeoDataFrame(geometry=[poly], crs="EPSG:4326")
    elif len(coords) >= 1:
        pt = Point(coords[0])
        poly = pt.buffer(0.01) # نطاق تقريبي ~1 كم
        return gpd.GeoDataFrame(geometry=[poly], crs="EPSG:4326")
    else:
        raise ValueError("تعذر استخراج الإحداثيات من الملف المرفوع. يرجى التأكد من تصدير الملف بصيغة KML من داخل التطبيق.")

# --- التنفيذ التلقائي ---
if st.button("🚀 جلب الحزم تلقائياً واستخراج القواطع"):
    if not uploaded_aoi:
        st.error("يرجى رفع ملف نطاق المنطقة من القائمة الجانبية أولاً.")
    elif len(date_range) < 2:
        st.error("يرجى تحديد بداية ونهاية الفترة الزمنية.")
    else:
        with st.spinner("جاري قراءة الملف وسحب الحزم الفضائية (Sentinel-2) سحابياً..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                try:
                    # 1. قراءة حدود المنطقة
                    aoi_gdf = load_aoi_file(uploaded_aoi.getbuffer(), uploaded_aoi.name, tmpdir).to_crs("EPSG:4326")
                    bounds = list(aoi_gdf.total_bounds) # [minx, miny, maxx, maxy]

                    # 2. البحث عن مرئيات Sentinel-2 سحابياً عبر STAC
                    catalog = pystac_client.Client.open(
                        "https://planetarycomputer.microsoft.com/api/stac/v1",
                        modifier=planetary_computer.sign_inplace,
                    )

                    start_date = date_range[0].strftime("%Y-%m-%d")
                    end_date = date_range[1].strftime("%Y-%m-%d")

                    search = catalog.search(
                        collections=["sentinel-2-l2a"],
                        bbox=bounds,
                        datetime=f"{start_date}/{end_date}",
                        query={"eo:cloud_cover": {"lt": max_cloud}},
                    )

                    items = list(search.items())
                    if not items:
                        st.error("لم يتم العثور على مرئيات فضائية خالية من الغيوم لهذه المنطقة في هذه الفترة.")
                    else:
                        item = items[0] # اختيار أفضل مرئية
                        
                        # 3. فتح الحزم مباشرة عبر روابط الشبكة وقصها
                        def fetch_band(asset_key):
                            href = item.assets[asset_key].href
                            with rasterio.open(href) as src:
                                aoi_reprojected = aoi_gdf.to_crs(src.crs)
                                geom = [aoi_reprojected.geometry.iloc[0]] if aoi_reprojected.geometry.iloc[0].geom_type in ['Polygon', 'MultiPolygon'] else [aoi_reprojected.unary_union.convex_hull]
                                data, out_transform = mask(src, geom, crop=True)
                                return data[0].astype(np.float32), out_transform, src.crs

                        swir2, transform, raster_crs = fetch_band("B12")
                        swir1, _, _ = fetch_band("B11")
                        nir, _, _ = fetch_band("B08")
                        red, _, _ = fetch_band("B04")

                        np.seterr(divide='ignore', invalid='ignore')

                        # 4. المعالجة والتحليل الطيفي
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
                        else:
                            st.warning("لم يتم العثور على خطوط مطابقة داخل نطاق هذا الملف.")
                except Exception as e:
                    st.error(f"حدث خطأ أثناء المعالجة: {str(e)}")
