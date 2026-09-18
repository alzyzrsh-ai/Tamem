import os
import numpy as np
import rasterio
from rasterio.enums import Resampling
import geopandas as gpd
from shapely.geometry import LineString
from sklearn.decomposition import PCA
from skimage.morphology import skeletonize
from skimage.filters import sobel
import matplotlib.pyplot as plt

# --- معالجة استدعاء الدالة لضمان التوافق مع كافة إصدارات scikit-image ---
try:
    from skimage.feature import meijering
except ImportError:
    try:
        from skimage.filters import meijering
    except ImportError:
        # حل بديل مستقر في حال اختلاف إصدار المكتبة على السيرفر
        from skimage.filters import frangi as meijering

def integrated_dyke_detection_system(
    swir2_path,
    swir1_path,
    nir_path,
    red_path,
    thermal_path,
    sar_path,
    dem_path,
    output_shp="extracted_dyke.shp",
    rose_diagram_png="dyke_rose_diagram.png"
):
    """
    منظومة معالجة متكاملة متوافقة مع بيئة Streamlit Cloud لكشف القواطع النارية.
    """
    print("[1/6] جاري قراءة البيانات وإعادة ضبط الأبعاد المكانية...")
    
    with rasterio.open(swir2_path) as src:
        swir2 = src.read(1).astype(np.float32)
        crs = src.crs
        transform = src.transform
        target_shape = swir2.shape

    def read_and_resample(path):
        if not path or not os.path.exists(path):
            return np.zeros(target_shape, dtype=np.float32)
        with rasterio.open(path) as src:
            return src.read(1, out_shape=target_shape, resampling=Resampling.bilinear).astype(np.float32)

    swir1 = read_and_resample(swir1_path)
    nir = read_and_resample(nir_path)
    red = read_and_resample(red_path)
    thermal = read_and_resample(thermal_path)
    sar = read_and_resample(sar_path)
    dem = read_and_resample(dem_path)

    np.seterr(divide='ignore', invalid='ignore')

    print("[2/6] معالجة المؤشرات الطيفية والحرارية...")
    ferrous_index = np.where(swir1 == 0, 0, swir2 / (swir1 + 1e-5))
    ndvi = np.where((nir + red) == 0, 0, (nir - red) / (nir + red + 1e-5))

    thermal_norm = (thermal - np.nanmin(thermal)) / (np.nanmax(thermal) - np.nanmin(thermal) + 1e-5)
    thermal_edges = sobel(thermal_norm)

    sar_norm = (sar - np.nanmin(sar)) / (np.nanmax(sar) - np.nanmin(sar) + 1e-5)
    sar_edges = sobel(sar_norm)

    print("[3/6] تطبيق تحليل المكونات الرئيسية (PCA)...")
    stacked_bands = np.stack([swir2, swir1, nir, red, thermal_norm], axis=-1)
    h, w, c = stacked_bands.shape
    flat_data = np.nan_to_num(stacked_bands.reshape(-1, c))

    pca = PCA(n_components=2)
    pcs = pca.fit_transform(flat_data)
    pc2_image = pcs[:, 1].reshape(h, w)

    print("[4/6] دمج الطبقات واستخراج الهيكل الخطي...")
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

    print("[5/6] تصدير ملف Shapefile...")
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
        gdf.to_file(output_shp, driver="ESRI Shapefile")
        print(f"تم تصدير Shapefile بنجاح: {output_shp}")

    print("[6/6] رسم مخطط الوردة الاتجاهي...")
    if angles:
        radii, edges = np.histogram(angles, bins=36, range=(0, 360))
        theta = np.deg2rad(edges[:-1])
        
        fig = plt.figure(figsize=(7, 7))
        ax = plt.subplot(111, projection='polar')
        ax.set_theta_zero_location('N')
        ax.set_theta_direction(-1)
        ax.bar(theta, radii, width=np.deg2rad(10), bottom=0.0, color='darkred', alpha=0.75, edgecolor='black')
        plt.title("مخطط الوردة الاتجاهي للخطوط والتراكيب المكتشفة", y=1.1)
        plt.savefig(rose_diagram_png, dpi=300, bbox_inches='tight')
        plt.close(fig)

    print("=== اكتملت المعالجة بنجاح ===")
