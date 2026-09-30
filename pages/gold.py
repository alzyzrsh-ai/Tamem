import ee

# 1. تهيئة بيئة Google Earth Engine
ee.Initialize()

# 2. تحديد منطقة الدراسة (حول مسجد لباده والأودية المجاورة)
center_point = ee.Geometry.Point([44.1522, 15.3120]) 
aoi = center_point.buffer(2500)  # نطاق 2.5 كم بدقة عالية

# =========================================================================
# أ) المرئيات البصرية وتحت الحمراء القصيرة (Sentinel-2) - 10m to 20m
# =========================================================================
s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
      .filterBounds(aoi)
      .filterDate('2025-01-01', '2026-09-30')
      .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 5))
      .median()
      .clip(aoi))

# مؤشرات أكسيد الحديد والتغير الطيني وعروق الكوارتز
iron_oxide = s2.select('B4').divide(s2.select('B2')).rename('Iron_Oxide')
clay_alteration = s2.select('B11').divide(s2.select('B12')).rename('Clay_Alteration')
silica_index = s2.select('B11').divide(s2.select('B8A')).rename('Silica_Index')

# =========================================================================
# ب) المرئيات الحرارية وتحت الحمراء الحرارية (Landsat 8/9 TIRS) - Thermal
# =========================================================================
landsat = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
           .filterBounds(aoi)
           .filterDate('2025-01-01', '2026-09-30')
           .filter(ee.Filter.lt('CLOUD_COVER', 5))
           .median()
           .clip(aoi))

# النطاق الحراري B10 (Thermal Infrared - Band 10) وتحويله لدرجات الحرارة السطحية/الانبعاثية
thermal_band = landsat.select('ST_B10').rename('Thermal_Infrared')

# =========================================================================
# ج) البيانات الرادارية (Sentinel-1 SAR Radar) - اختراق التربة السطحية
# =========================================================================
s1_radar = (ee.ImageCollection('COPERNICUS/S1_GRD')
            .filterBounds(aoi)
            .filter(ee.Filter.eq('instrumentMode', 'IW'))
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
            .median()
            .select('VV')
            .clip(aoi))

# تنعيم الإشارة الرادارية لكشف التراكيب والمجاري المطمورة تحت الرواسب
radar_paleochannels = s1_radar.focal_mean(50, 'circle', 'meters').rename('Radar_Channels')

# =========================================================================
# د) المعالجة التضاريسية والهيدرولوجية (ALOS DEM) - المصايد التضاريسية
# =========================================================================
dem = ee.Image('JAXA/ALOS/AW3D30/V3_2').select('DSM').clip(aoi)
slope = ee.Terrain.slope(dem)

# تحديد نقاط هبوط السرعة الانحدارية (مناطق الترسيب: انحدار 1 - 3 درجات)
gold_traps = slope.gte(1).And(slope.lte(3)).rename('Gold_Traps')

# =========================================================================
# هـ) التجميع الموزون والدمج المتكامل (Multi-Sensor Overlay)
# =========================================================================
# دمج الطيفي + الحراري + الراداري + التضاريسي
comprehensive_gold_score = (
    iron_oxide.multiply(0.25)
    .add(clay_alteration.multiply(0.20))
    .add(silica_index.multiply(0.15))
    .add(thermal_band.multiply(0.15))      # إضافة البصمة الحرارية
    .add(radar_paleochannels.multiply(0.15)) # إضافة البيانات الرادارية
    .add(gold_traps.multiply(0.10))
).rename('Comprehensive_Gold_Index')

# =========================================================================
# و) استخراج أعلى 3% من الشذوذات النقطية الدقيقة للتطبيق الميداني
# =========================================================================
percentile_97 = comprehensive_gold_score.reduceRegion(
    reducer=ee.Reducer.percentile([97]),
    geometry=aoi,
    scale=10
).get('Comprehensive_Gold_Index')

high_anomaly_mask = comprehensive_gold_score.gte(ee.Number(percentile_97))

# تحويل الشذوذات النقطية إلى متجهات لإصدار ملف KML للهاتف
anomaly_points = high_anomaly_mask.selfMask().reduceToVectors(
    geometry=aoi,
    scale=10,
    geometryType='point',
    eightConnected=False
)

print("تم تنفيذ معالجة الدمج المتكامل (بصري + حراري + راداري + تضاريسي) بنجاح.")
