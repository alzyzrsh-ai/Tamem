import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import ee
import geemap
from sklearn.ensemble import RandomForestRegressor

# ==========================================
# 1. تفريغ ومعالجة بيانات الجسة الميدانية (VES No. 2)
# ==========================================

# إحداثيات الجسة من واقع التقرير المرفق (UTM Zone 38N)
utm_easting = 330407
utm_northing = 1558564
elevation_masl = 208

# جدول القراءات الميدانية الجيوكهربائية (Schlumberger Array)
ves2_data = {
    'MN/2': [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 10, 0.5, 10, 10, 
             10, 10, 10, 50, 10, 50, 50, 50, 50, 50, 50, 50],
    'AB/2': [1.5, 2.5, 4, 6, 8, 10, 15, 20, 30, 40, 40, 50, 
             75, 100, 160, 150, 200, 200, 300, 400, 500, 600, 700, 800],
    'Rho_a': [428.3, 382.6, 369.5, 319.8, 330.0, 349.3, 342.8, 315.4, 311.3, 302.2, 
              245.3, 210.0, 166.7, 135.8, 68.2, 73.0, 50.0, 38.1, 15.2, 14.9, 16.5, 25.1, 10.6, 22.4]
}

df_ves = pd.DataFrame(ves2_data)

# رسم منحنى الجسة الجيوكهربائية Log-Log Plot
plt.figure(figsize=(9, 5))
plt.loglog(df_ves['AB/2'], df_ves['Rho_a'], 'ro-', label='VES No. 2 Measured')
plt.xlabel('Half Electrode Spacing AB/2 (m)')
plt.ylabel('Apparent Resistivity $\\rho_a$ (Ohm.m)')
plt.title(f'Sounding Curve - VES No. 2 (UTM-E: {utm_easting}, UTM-N: {utm_northing})')
plt.grid(True, which="both", ls="--")
plt.legend()
plt.show()

# حساب متوسط المقاومية الفعالة للطبقة العميقة المشبعة (AB/2 >= 200m)
target_aquifer_resistivity = df_ves[df_ves['AB/2'] >= 200]['Rho_a'].mean()
print(f"المقاومية المستهدفة للنطاق العميق المشبع: {target_aquifer_resistivity:.2f} Ohm.m")

# ==========================================
# 2. ربط الجسة بالبيانات الفضائية عبر Earth Engine
# ==========================================

# تهيئة Google Earth Engine
ee.Initialize()

# الإحداثيات الجغرافية المكافئة للنقطة (WGS84 - Zone 38N)
lon, lat = 43.4295812, 14.0931013
ves_point = ee.Geometry.Point([lon, lat])
roi = ves_point.buffer(5000) # نطاق دراسة 5 كم حول الجسة

# جلب بيانات الرادار Sentinel-1 (SAR)
sar = (ee.ImageCollection('COPERNICUS/S1_GRD')
       .filterBounds(roi)
       .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
       .filter(ee.Filter.eq('instrumentMode', 'IW'))
       .select('VV')
       .mean().clip(roi))

# جلب بيانات الحرارة السطحية LST من Landsat 8/9
landsat = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
           .filterBounds(roi)
           .filter(ee.Filter.lt('CLOUD_COVER', 15))
           .median())

lst = landsat.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15).clip(roi)

# النموذج الرقمي للارتفاعات والانحراف الطبوغرافي DEM & Slope
dem = ee.Image('USGS/SRTMGL1_003').clip(roi)
slope = ee.Terrain.slope(dem)

# دمج الطبقات الفضائية
stack_image = ee.Image.cat([
    sar.rename('SAR_VV'), 
    lst.rename('LST'), 
    dem.rename('ELEVATION'), 
    slope.rename('SLOPE')
])

# استخراج القراءات الفضائية بالضبط عند موقع الجسة
features_at_ves = stack_image.reduceRegion(
    reducer=ee.Reducer.first(),
    geometry=ves_point,
    scale=30
).getInfo()

print("المؤشرات الفضائية المستخرجة عند موقع الجسة:")
print(features_at_ves)

# ==========================================
# 3. تدريب النموذج والتنبؤ التفاعلي
# ==========================================

# إعداد مصفوفة التناظر للتدريب (X: الفضائي -> y: المقاومية الأرضية)
X_train = np.array([[
    features_at_ves['SAR_VV'], 
    features_at_ves['LST'], 
    features_at_ves['ELEVATION'], 
    features_at_ves['SLOPE']
]])
y_train = np.array([target_aquifer_resistivity])

# إنشاء خوارزمية التنبؤ
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# عرض النتيجة والطبقات الفضائية على خريطة تفاعلية
Map = geemap.Map()
Map.centerObject(ves_point, 13)

Map.addLayer(sar, {'min': -20, 'max': -2}, 'SAR Backscatter (VV)')
Map.addLayer(lst, {'min': 20, 'max': 45, 'palette': ['blue', 'yellow', 'red']}, 'Surface Temp (°C)')
Map.addLayer(ves_point, {'color': 'red'}, 'VES No. 2 Location')

Map
