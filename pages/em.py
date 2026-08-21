import os
import urllib.request
import numpy as np
import pandas as pd
import xarray as xr
import rasterio
from rasterio.transform import from_origin
from pyproj import Transformer
from scipy.fft import fft2, ifft2, fftshift

# ==========================================
# 1. واجهة إدخال الإحداثيات واستجلاب البيانات
# ==========================================
def fetch_emag2_data(min_x, max_x, min_y, max_y, is_utm=False, utm_epsg=32638):
    """
    تحميل بيانات EMAG2 V2 بناءً على الإحداثيات المدخلة.
    تستقبل UTM أو Decimal Degrees وتُرجع xarray Dataset.
    """
    # تحويل الإحداثيات إلى WGS84 (Lat/Lon) إذا كانت مدخلة بـ UTM
    if is_utm:
        transformer = Transformer.from_crs(f"epsg:{utm_epsg}", "epsg:4326", always_xy=True)
        lon_min, lat_min = transformer.transform(min_x, min_y)
        lon_max, lat_max = transformer.transform(max_x, max_y)
    else:
        lon_min, lon_max, lat_min, lat_max = min_x, max_x, min_y, max_y

    print(f"[-] نطاق الإحداثيات الجغرافية: Lon ({lon_min:.4f} to {lon_max:.4f}), Lat ({lat_min:.4f} to {lat_max:.4f})")

    # رابط تنزيل شبكة EMAG2 V2 العالمية (صيغة NetCDF)
    url = "https://www.ngdc.noaa.gov/geomag/data/EMAG2/EMAG2_V2_20090519.nc"
    local_file = "EMAG2_V2.nc"

    if not os.path.exists(local_file):
        print("[-] جاري تحميل شبكة EMAG2 العالمية لأول مرة (قد يستغرق دقائق)...")
        urllib.request.urlretrieve(url, local_file)
        print("[+] تم التحميل بنجاح.")

    # فتح الملف وقص المنطقة المحددة
    ds = xr.open_dataset(local_file)
    
    # التعامل مع تسميات المحاور في NetCDF
    lon_name = 'lon' if 'lon' in ds.coords else 'longitude'
    lat_name = 'lat' if 'lat' in ds.coords else 'latitude'
    
    cropped_ds = ds.sel(
        {lon_name: slice(lon_min, lon_max), lat_name: slice(lat_min, lat_max)}
    )
    return cropped_ds, (lon_min, lon_max, lat_min, lat_max)

# ==========================================
# 2. التصدير إلى Excel و GeoTIFF
# ==========================================
def export_to_excel_and_geotiff(ds, output_prefix="magnetic_data"):
    # استخراج المصفوفات
    lon = ds['lon'].values if 'lon' in ds.coords else ds['longitude'].values
    lat = ds['lat'].values if 'lat' in ds.coords else ds['latitude'].values
    
    # افتراض اسم متغير الشذوذ المغناطيسي z أو z_anomaly
    var_name = list(ds.data_vars)[0]
    mag_grid = ds[var_name].values

    # --- تصدير Excel (XYZ Format) ---
    lon_grid, lat_grid = np.meshgrid(lon, lat)
    df = pd.DataFrame({
        'Longitude': lon_grid.flatten(),
        'Latitude': lat_grid.flatten(),
        'TMI_Anomaly_nT': mag_grid.flatten()
    })
    excel_path = f"{output_prefix}.xlsx"
    df.to_excel(excel_path, index=False)
    print(f"[+] تم تصدير البيانات إلى Excel: {excel_path}")

    # --- تصدير GeoTIFF ---
    geotiff_path = f"{output_prefix}.tif"
    res_x = (lon[-1] - lon[0]) / (len(lon) - 1)
    res_y = (lat[-1] - lat[0]) / (len(lat) - 1)
    transform = from_origin(lon[0], lat[-1], res_x, res_y)

    with rasterio.open(
        geotiff_path, 'w',
        driver='GTiff',
        height=mag_grid.shape[0],
        width=mag_grid.shape[1],
        count=1,
        dtype=mag_grid.dtype,
        crs='EPSG:4326',
        transform=transform,
    ) as dst:
        dst.write(np.flipud(mag_grid), 1)
    print(f"[+] تم تصدير البيانات إلى GeoTIFF: {geotiff_path}")

    return mag_grid, res_x * 111000 # تحويل الدقة القوسية تقريبياً إلى أمتار

# ==========================================
# 3. معالجات استنباط صخور القاعدة والتراكيب
# ==========================================
def process_subsurface_structures(mag_data, dx):
    """
    حساب المشتقة الرأسية (FVD) والإشارة التحليلية (Analytic Signal) للكشف عن الصدوع وصخور القاعدة
    """
    ny, nx = mag_data.shape
    kx = 2 * np.pi * np.fft.fftfreq(nx, d=dx)
    ky = 2 * np.pi * np.fft.fftfreq(ny, d=dx)
    KX, KY = np.meshgrid(kx, ky)
    K = np.sqrt(KX**2 + KY**2)

    data_ft = fft2(mag_data)

    # 1. المشتقة الرأسية الأولى (First Vertical Derivative - FVD)
    fvd_ft = data_ft * K
    fvd = np.real(ifft2(fvd_ft))

    # 2. المشتقات الأفقية (Horizontal Derivatives)
    dx_ft = data_ft * (1j * KX)
    dy_ft = data_ft * (1j * KY)
    dx_map = np.real(ifft2(dx_ft))
    dy_map = np.real(ifft2(dy_ft))

    # 3. الإشارة التحليلية (Analytic Signal) - تحدد حدود كتل صخور القاعدة والصدوع القاطعة
    analytic_signal = np.sqrt(dx_map**2 + dy_map**2 + fvd**2)

    # 4. زاوية الميل (Tilt Derivative) - تبرز التراكيب الضحلة والعميقة معاً
    tilt_angle = np.arctan2(fvd, np.sqrt(dx_map**2 + dy_map**2))

    return {
        'FVD': fvd,
        'Analytic_Signal': analytic_signal,
        'Tilt_Angle': tilt_angle
    }

# ==========================================
# 4. تشغيل البرنامج عبر ادخال الاحداثيات
# ==========================================
if __name__ == "__main__":
    print("=== برنامج جلب ومعالجة البيانات المغناطيسية الفضائية ===")
    
    # اختيار نظام الإحداثيات
    choice = input("هل تريد إدخال الإحداثيات بـ (1) UTM أو (2) خطوط الطول والعرف Lat/Lon؟ [اختر 1 أو 2]: ")
    
    if choice == '1':
        epsg = int(input("أدخل رمز EPSG لمنطقة UTM (مثال اليمن Zone 38N هو 32638): "))
        min_x = float(input("أدخل Min X (Easting): "))
        max_x = float(input("أدخل Max X (Easting): "))
        min_y = float(input("أدخل Min Y (Northing): "))
        max_y = float(input("أدخل Max Y (Northing): "))
        is_utm = True
    else:
        min_x = float(input("أدخل أقل خط طول (Min Longitude): "))
        max_x = float(input("أدخل أعلى خط طول (Max Longitude): "))
        min_y = float(input("أدخل أقل خط عرض (Min Latitude): "))
        max_y = float(input("أدخل أعلى خط عرض (Max Latitude): "))
        is_utm = False
        epsg = 4326

    # 1. تنزيل وقص البيانات
    ds_cropped, bounds = fetch_emag2_data(min_x, max_x, min_y, max_y, is_utm=is_utm, utm_epsg=epsg)

    # 2. التصدير إلى Excel و GeoTIFF
    mag_grid, cell_size_m = export_to_excel_and_geotiff(ds_cropped, output_prefix="subsurface_mag_region")

    # 3. المعالجة واستنباط التراكيب وصخور القاعدة
    print("[-] جاري تنفيذ معالجات التراكيب تحت السطحية والإشارة التحليلية...")
    results = process_subsurface_structures(mag_grid, dx=cell_size_m)

    print("\n[✔] اكتملت العمليات بنجاح!")
    print(" - الملف الرقمي: subsurface_mag_region.xlsx")
    print(" - الخريطة المرجعية: subsurface_mag_region.tif")
    print(" - تم استنباط المشتقات الرأسية (FVD) والإشارة التحليلية (Analytic Signal) وزاوية الميل (Tilt Angle).")
