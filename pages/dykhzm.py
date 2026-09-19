import os
import re
import zipfile
import tempfile
import xml.etree.ElementTree as ET
from datetime import date
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from scipy.ndimage import zoom
from shapely.geometry import LineString, Point, Polygon, box
from sklearn.decomposition import PCA
from skimage.morphology import skeletonize
from skimage.filters import sobel
import matplotlib.pyplot as plt
import streamlit as st

# مكتبات العرض الخرائطي والجلب
import folium
from streamlit_folium import st_folium
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
st.info("💡 ارفع ملف المنطقة (AlpineQuest / KML / KMZ / WPT) أو أدخل الإحداثيات يدوياً لجلب الحزم الفضائية ومعالجتها سحابياً.")

# --- القائمة الجانبية ---
st.sidebar.header("🗺️ 1. تحديد نطاق الدراسة")
input_method = st.sidebar.radio("طريقة تحديد المنطقة:", ["رفع ملف (KML / KMZ / WPT)", "إدخال إحداثيات يدوياً"])

uploaded_aoi = None
manual_mode = None
lat_center, lon_center, buffer_km = 0.0, 0.0, 5.0
min_lat, max_lat, min_lon, max_lon = 0.0, 0.0, 0.0, 0.0

if input_method == "رفع ملف (KML / KMZ / WPT)":
    uploaded_aoi = st.sidebar.file_uploader("ارفع ملف النطاق", type=["kml", "kmz", "wpt", "ldk"])
else:
    manual_mode = st.sidebar.selectbox("نوع الإدخال اليدوي:", ["نقطة مركزية + نصف قطر (كم)", "مربع إحاطة (Min/Max)"])
    if manual_mode == "نقطة مركزية + نصف قطر (كم)":
        lat_center = st.sidebar.number_input("خط العرض (Latitude):", value=15.3547, format="%.6f")
        lon_center = st.sidebar.number_input("خط الطول (Longitude):", value=44.2066, format="%.6f")
        buffer_km = st.sidebar.number_input("نصف القطر (كيلومتر):", value=5.0, min_value=0.5, max_value=50.0)
    else:
        col1, col2 = st.sidebar.columns(2)
        with col1:
            min_lat = st.number_input("أدنى عرض (Min Lat):", value=15.3000, format="%.4f")
            min_lon = st.number_input("أدنى طول (Min Lon):", value=44.1500, format="%.4f")
        with col2:
            max_lat = st.number_input("أقصى عرض (Max Lat):", value=15.4000, format="%.4f")
            max_lon = st.number_input("أقصى طول (Max Lon):", value=44.2500, format="%.4f")

st.sidebar.header("⚙️ 2. خيارات السحب")
date_range = st.sidebar.date_input("الفترة الزمنية للمرئيات:", [date(2023, 1, 1), date(2026, 1, 1)])
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
        try:
            return gpd.read_file(file_path)
        except Exception:
            pass

    coords = []
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        for elem in root.iter():
            if elem.tag.endswith('coordinates') and elem.text:
                raw_coords = elem.text.strip().split()
                for c in raw_coords:
                    parts = c.split(',')
                    if len(parts) >= 2:
                        lon, lat = float(parts[0]), float(parts[1])
                        if -180 <= lon <= 180 and -90 <= lat <= 90:
                            coords.append((lon, lat))
    except Exception:
        pass

    if not coords:
        try:
            content = file_bytes.decode('utf-8', errors='ignore')
            if not content:
                content = file_bytes.decode('latin-1', errors='ignore')
            
            matches = re.findall(r'([-+]?\d{1,3}\.\d{3,10})[\s,]+([-+]?\d{1,2}\.\d{3,10})', content)
            for val1, val2 in matches:
                v1, v2 = float(val1), float(val2)
                if -180 <= v1 <= 180 and -90 <= v2 <= 90:
                    coords.append((v1, v2))
                elif -180 <= v2 <= 180 and -90 <= v1 <= 90:
                    coords.append((v2, v1))
        except Exception:
            pass

    if len(coords) >= 3:
        poly = Polygon(coords)
        return gpd.GeoDataFrame(geometry=[poly], crs="EPSG:4326")
    elif len(coords) >= 1:
        pt = Point(coords[0])
        poly = pt.buffer(0.02)
        return gpd.GeoDataFrame(geometry=[poly], crs="EPSG:4326")
    else:
        raise ValueError("تعذر قراءة الملف. يرجى استخدام خيار 'إدخال إحداثيات يدوياً' من القائمة الجانبية.")

def build_manual_gdf():
    if manual_mode == "نقطة مركزية + نصف قطر (كم)":
        pt = Point(lon_center, lat_center)
        buffer_deg = buffer_km / 111.0
        poly = pt.buffer(buffer_deg)
        return gpd.GeoDataFrame(geometry=[poly], crs="EPSG:4326")
    else:
        poly = box(min_lon, min_lat, max_lon, max_lat)
        return gpd.GeoDataFrame(geometry=[poly], crs="EPSG:4326")

# --- التنفيذ التلقائي ---
if st.button("🚀 جلب الحزم تلقائياً واستخراج القواطع"):
    if input_method == "رفع ملف (KML / KMZ / WPT)" and not uploaded_aoi:
        st.error("يرجى رفع ملف نطاق المنطقة أو التحويل للوضع اليدوي من القائمة الجانبية.")
    elif len(date_range) < 2:
        st.error("يرجى تحديد بداية ونهاية الفترة الزمنية.")
    else:
        with st.spinner("جاري إعداد المنطقة وسحب الحزم الفضائية (Sentinel-2) سحابياً..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                try:
                    if input_method == "رفع ملف (KML / KMZ / WPT)":
                        aoi_gdf = load_aoi_file(uploaded_aoi.getbuffer(), uploaded_aoi.name, tmpdir).to_crs("EPSG:4326")
                    else:
                        aoi_gdf = build_manual_gdf()

                    bounds = list(aoi_gdf.total_bounds)

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
                        item = items[0]
                        
                        # دالة سحب وصياغة الحزم
                        def fetch_band(asset_key, target_shape=None):
                            href = item.assets[asset_key].href
                            with rasterio.open(href) as src:
                                aoi_reprojected = aoi_gdf.to_crs(src.crs)
                                geom = [aoi_reprojected.geometry.iloc[0]] if aoi_reprojected.geometry.iloc[0].geom_type in ['Polygon', 'MultiPolygon'] else [aoi_reprojected.unary_union.convex_hull]
                                
                                data, out_transform = mask(src, geom, crop=True)
                                band_data = data[0].astype(np.float32)

                                if target_shape is not None and band_data.shape != target_shape:
                                    zoom_factors = (target_shape[0] / band_data.shape[0], target_shape[1] / band_data.shape[1])
                                    band_data = zoom(band_data, zoom_factors, order=1)

                                return band_data, out_transform, src.crs, band_data.shape

                        swir2, transform, raster_crs, ref_shape = fetch_band("B12")
                        swir1, _, _, _ = fetch_band("B11", target_shape=ref_shape)
                        nir, _, _, _ = fetch_band("B08", target_shape=ref_shape)
                        red, _, _, _ = fetch_band("B04", target_shape=ref_shape)

                        np.seterr(divide='ignore', invalid='ignore')

                        # المعالجة
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

                        # استخراج الخطوط
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

                        st.success("✅ تم جلب الحزم واستخراج القواطع بنجاح!")

                        # --- قسم 1: معاينة وتنزيل الحزم الفضائية المجلوبة ---
                        st.subheader("📡 الحزم الفضائية المجلوبة (Sentinel-2)")
                        tab1, tab2, tab3, tab4 = st.tabs(["الحزمة B12 (SWIR2)", "الحزمة B11 (SWIR1)", "الحزمة B08 (NIR)", "الحزمة B04 (Red)"])
                        
                        with tab1:
                            fig_b12, ax_b12 = plt.subplots(figsize=(6, 4))
                            im12 = ax_b12.imshow(swir2, cmap='gray')
                            plt.colorbar(im12, ax=ax_b12)
                            st.pyplot(fig_b12)
                        
                        with tab2:
                            fig_b11, ax_b11 = plt.subplots(figsize=(6, 4))
                            im11 = ax_b11.imshow(swir1, cmap='gray')
                            plt.colorbar(im11, ax=ax_b11)
                            st.pyplot(fig_b11)

                        with tab3:
                            fig_b8, ax_b8 = plt.subplots(figsize=(6, 4))
                            im8 = ax_b8.imshow(nir, cmap='gray')
                            plt.colorbar(im8, ax=ax_b8)
                            st.pyplot(fig_b8)

                        with tab4:
                            fig_b4, ax_b4 = plt.subplots(figsize=(6, 4))
                            im4 = ax_b4.imshow(red, cmap='gray')
                            plt.colorbar(im4, ax=ax_b4)
                            st.pyplot(fig_b4)

                        # --- قسم 2: خريطة الإسقاط الميداني للتطبيقات والمواقع ---
                        if lines:
                            gdf = gpd.GeoDataFrame(geometry=lines, crs=raster_crs)
                            gdf_wgs84 = gdf.to_crs("EPSG:4326")

                            st.subheader("🗺️ إسقاط القواطع المكتشفة على خريطة المنطقة")
                            
                            # تحديد مركز الخريطة
                            centroid = aoi_gdf.unary_union.centroid
                            m = folium.Map(location=[centroid.y, centroid.x], zoom_start=13, tiles="OpenStreetMap")
                            
                            # إضافة صور القمار الصناعية ESRI Satellite كطبقة أساسية
                            folium.TileLayer(
                                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                                attr='Esri',
                                name='صورة فضائية (Esri Satellite)',
                                overlay=False,
                                control=True
                            ).add_to(m)

                            # رسم القواطع باللون الأحمر على الخريطة
                            folium.GeoJson(
                                gdf_wgs84,
                                name="القواطع النارية المكتشفة",
                                style_function=lambda x: {'color': 'red', 'weight': 2.5, 'opacity': 0.8}
                            ).add_to(m)

                            folium.LayerControl().add_to(m)
                            st_folium(m, width=900, height=500)

                            # ملف التنزيل SHP
                            zip_path = os.path.join(tmpdir, "dykes_auto.zip")
                            shp_dir = os.path.join(tmpdir, "shp")
                            os.makedirs(shp_dir, exist_ok=True)
                            gdf.to_file(os.path.join(shp_dir, "dykes.shp"), driver="ESRI Shapefile")

                            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                                for root, _, files in os.walk(shp_dir):
                                    for file in files:
                                        zipf.write(os.path.join(root, file), file)

                            st.download_button(
                                label="📥 تحميل Shapefile المكتشف (ZIP)",
                                data=open(zip_path, "rb"),
                                file_name="extracted_dykes.zip",
                                mime="application/zip"
                            )

                            if angles:
                                st.subheader("📊 مخطط الوردة الاتجاهي")
                                radii, edges = np.histogram(angles, bins=36, range=(0, 360))
                                theta = np.deg2rad(edges[:-1])
                                
                                fig = plt.figure(figsize=(5, 5))
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
