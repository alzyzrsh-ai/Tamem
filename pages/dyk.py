import os
import numpy as np
import rasterio
from rasterio.enums import Resampling
import geopandas as gpd
from shapely.geometry import LineString
from sklearn.decomposition import PCA
from skimage.feature import meijering
from skimage.morphology import skeletonize
from skimage.filters import sobel
import matplotlib.pyplot as plt

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
    منظومة متكاملة لكشف القواطع النارية المدفونة باستخدام المعالجة الطيفية، الحرارية، 
    الرادارية، والتضاريسية، مع التصدير المتجهي والتحليل الهيكلي.
    """
    print("[1/6] جاري قراءة البيانات وإعادة ضبط الأبعاد المكانية...")
    
    # 1. قراءة المرجع المكاني والأبعاد الرئيسية من حزمة SWIR2
    with rasterio.open(swir2_path) as src:
        swir2 = src.read(1).astype(np.float32)
        crs = src.crs
        transform = src.transform
        target_shape = swir2.shape

    # دالة مساعدة لقص وإعادة تعيين أبعاد الطبقات لتتطابق تماماً
    def read_and_resample(path):
        if not path or not os.path.exists(path):
            print(f"تنبيه: الملف {path} غير موجود، سيتم تعويضه بصفوف أصفار.")
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

    print("[2/6] معالجة المؤشرات الطيفية والحرارية والبحث عن الشذوذات...")
    
    # أ) نسبة المعادن الحديدية والمافية (Ferrous Index)
    ferrous_index = np.where(swir1 == 0, 0, swir2 / (swir1 + 1e-5))
    
    # ب) مؤشر الغطاء النباتي والرطوبة الخطية (NDVI)
    ndvi = np.where((nir + red) == 0, 0, (nir - red) / (nir + red + 1e-5))

    # ج) التباين الحراري السطحي (Thermal Contrast)
    thermal_norm = (thermal - np.nanmin(thermal)) / (np.nanmax(thermal) - np.nanmin(thermal) + 1e-5)
    thermal_edges = sobel(thermal_norm)

    # د) معالجة مرئية الرادار (SAR - Surface Roughness)
    sar_norm = (sar - np.nanmin(sar)) / (np.nanmax(sar) - np.nanmin(sar) + 1e-5)
    sar_edges = sobel(sar_norm)

    print("[3/6] تطبيق تحليل المكونات الرئيسية (PCA)...")
    
    # دمج الحزم في مصفوفة واحدة لتطوير PCA
    stacked_bands = np.stack([swir2, swir1, nir, red, thermal_norm], axis=-1)
    h, w, c = stacked_bands.shape
    flat_data = np.nan_to_num(stacked_bands.reshape(-1, c))

    pca = PCA(n_components=2)
    pcs = pca.fit_transform(flat_data)
    pc2_image = pcs[:, 1].reshape(h, w) # المكون الثاني لإبراز الشذوذات الخطيّة

    print("[4/6] التجميع التكاملي للطبقات واستخراج الهيكل الخطي...")
    
    # مصفوفة الأوزان المتكاملة (Multisensor Integration)
    integrated_feature = (
        sobel(ferrous_index) * 0.20 + 
        sobel(ndvi) * 0.10 + 
        thermal_edges * 0.20 + 
        sar_edges * 0.15 + 
        sobel(pc2_image) * 0.20 + 
        sobel(dem) * 0.15
    )

    # كشف المسارات المرتفعة الهيكلية وتحويلها لتغطية ثنائية بعرض بكسل واحد
    ridges = meijering(integrated_feature, sigmas=[1, 2, 3], black_ridges=False)
    binary_lineaments = ridges > np.percentile(ridges, 93)
    skeleton = skeletonize(binary_lineaments)

    print("[5/6] تحويل البكسلات الخطية وتصدير ملف Shapefile...")
    
    lines = []
    angles = []
    rows, cols = np.where(skeleton)

    for r, c in zip(rows, cols):
        x1, y1 = rasterio.transform.xy(transform, r, c)
        x2, y2 = rasterio.transform.xy(transform, r + 1, c + 1)
        lines.append(LineString([(x1, y1), (x2, y2)]))
        
        # حساب الزاوية الاتجاهية لكل جزء خطي
        dx = x2 - x1
        dy = y2 - y1
        angle = np.degrees(np.arctan2(dx, dy)) % 360
        angles.append(angle)

    if lines:
        gdf = gpd.GeoDataFrame(geometry=lines, crs=crs)
        gdf = gdf.dissolve()
        gdf.to_file(output_shp, driver="ESRI Shapefile")
        print(f"-> تم حفظ التراكيب الخطية المكتشفة بنجاح في: {output_shp}")
    else:
        print("-> لم يتم كشف خطوط مطابقة للشروط.")

    print("[6/6] رسم وإنشاء مخطط الوردة الاتجاهي (Rose Diagram)...")
    
    if angles:
        radii, edges = np.histogram(angles, bins=36, range=(0, 360))
        theta = np.deg2rad(edges[:-1])
        
        plt.figure(figsize=(7, 7))
        ax = plt.subplot(111, projection='polar')
        ax.set_theta_zero_location('N') # اتجاه الشمال في الأعلى
        ax.set_theta_direction(-1)     # مع عقارب الساعة
        ax.bar(theta, radii, width=np.deg2rad(10), bottom=0.0, color='darkred', alpha=0.75, edgecolor='black')
        plt.title("مخطط الوردة الاتجاهي للخطوط والتراكيب المكتشفة\n(Lineament Trend Analysis)", y=1.1)
        plt.savefig(rose_diagram_png, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"-> تم حفظ مخطط الاتجاهات بنجاح في: {rose_diagram_png}")

    print("=== اكتملت المعالجة بنجاح ===")

# ==========================================
# مثال على كيفية استدعاء وتشغيل المنظومة:
# ==========================================
if __name__ == "__main__":
    integrated_dyke_detection_system(
        swir2_path="B12.tif",         # Sentinel-2 Band 12 / Landsat 8 Band 7
        swir1_path="B11.tif",         # Sentinel-2 Band 11 / Landsat 8 Band 6
        nir_path="B08.tif",           # Sentinel-2 Band 8  / Landsat 8 Band 5
        red_path="B04.tif",           # Sentinel-2 Band 4  / Landsat 8 Band 4
        thermal_path="B10_TIR.tif",   # Landsat 8 Thermal Band 10
        sar_path="Sentinel1_VH.tif",  # Sentinel-1 SAR Radar (VH/VV)
        dem_path="Copernicus_DEM.tif",# DEM 30m or better
        output_shp="dyke_lineaments.shp",
        rose_diagram_png="dyke_rose_diagram.png"
    )
