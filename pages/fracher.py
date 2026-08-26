import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes
from shapely.geometry import LineString, shape
from shapely.ops import linemerge
from skimage.morphology import remove_small_objects, skeletonize

# --- 1. تحديد المسارات ---
input_raster = "Automateفركشؤ الصفراءd_Fracture_Raster.tif"
output_shapefile = "Extracted_Faults_Vector.shp"

# --- 2. قراءة الراستر ونظام الإحداثيات (CRS) ---
with rasterio.open(input_raster) as src:
    img = src.read(1)
    transform = src.transform
    crs = src.crs

# --- 3. معالجة وتصفية الضوضاء (Noise Filtering) ---
binary_mask = img > 0
# إزالة التكتلات والبكسلات المعزولة الصغيرة (أقل من 15 بكسل مثلاً)
cleaned_mask = remove_small_objects(binary_mask, min_size=15)

# --- 4. جعل سمك الخطوط بكسل واحد (Skeletonization) ---
skeleton = skeletonize(cleaned_mask).astype(np.uint8)

# --- 5. تحويل البكسلات الهيكلية إلى متجهات (Vector Geometry) ---
results = (
    {"properties": {"raster_val": v}, "geometry": s}
    for i, (s, v) in enumerate(
        shapes(skeleton, mask=skeleton, transform=transform)
    )
)

geoms = list(results)
polygons = [shape(g["geometry"]) for g in geoms]

# --- 6. استخراج الخطوط المحورية (Centerlines/Lines) وحساب الخصائص ---
lines = []
for poly in polygons:
    # استخراج الحدود للكسور المجمعة
    line = poly.boundary
    if line.geom_type == "LineString":
        lines.append(line)
    elif line.geom_type == "MultiLineString":
        lines.extend(list(line.geoms))

# دمج الأجزاء المتصلة في خطوط موحدة
merged_lines = linemerge(lines)
if merged_lines.geom_type == "LineString":
    final_lines = [merged_lines]
else:
    final_lines = list(merged_lines.geoms)

# --- 7. إنشاء GeoDataFrame وحفظ الشيب فايل النهائي ---
gdf = gpd.GeoDataFrame(geometry=final_lines, crs=crs)

# إضافة حقل لحساب طول كل صدع/كسر (بالأمتار إذا كان نظام الإحداثيات مترياً)
gdf["Length_m"] = gdf.length

# إعادة إسقاط إلى WGS84 (EPSG:4326) لضمان القابلية للفتح في Google Earth/Engine أو محركات البحث الجغرافية
gdf_wgs84 = gdf.to_crs(epsg=4326)

# حفظ الملف بصيغة Shapefile
gdf.to_file(output_shapefile)
# حفظ نسخة أخرى بصيغة GeoJSON (سهلة الفتح والاستخدام في تطبيقات الويب ومحركات البحث الجغرافية)
gdf_wgs84.to_file("Extracted_Faults_WGS84.geojson", driver="GeoJSON")

print(
    f" تم استخراج الصدوع بنجاح وتصديرها إلى الشيب فايل: {output_shapefile}"
)
