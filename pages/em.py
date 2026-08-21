import streamlit as st
import numpy as np
import pandas as pd
import rasterio
from io import BytesIO
from pyproj import Transformer
from scipy.fft import fft2, ifft2

st.set_page_config(page_title="استكشاف المغناطيسية وصخور القاعدة", layout="wide")

st.title("🧲 استكشاف البيانات المغناطيسية واستنباط صخور القاعدة")
st.write("أدخل إحداثيات المنطقة لقص البيانات المغناطيسية (EMAG2)، تصديرها، واستنباط التراكيب تحت السطحية.")

# ==========================================
# 1. شريط الإعدادات والإحداثيات
# ==========================================
st.sidebar.header("إعدادات الإحداثيات")
coord_type = st.sidebar.radio("نظام الإحداثيات:", ["UTM", "جغرافي (Lat/Lon)"])

if coord_type == "UTM":
    epsg = st.sidebar.number_input("EPSG Code (مثال اليمن Zone 38N = 32638):", value=32638)
    min_x = st.sidebar.number_input("Min X (Easting):", value=200000.0)
    max_x = st.sidebar.number_input("Max X (Easting):", value=250000.0)
    min_y = st.sidebar.number_input("Min Y (Northing):", value=1500000.0)
    max_y = st.sidebar.number_input("Max Y (Northing):", value=1550000.0)
else:
    epsg = 4326
    min_x = st.sidebar.number_input("أقل خط طول (Min Longitude):", value=43.0)
    max_x = st.sidebar.number_input("أعلى خط طول (Max Longitude):", value=44.0)
    min_y = st.sidebar.number_input("أقل خط عرض (Min Latitude):", value=13.5)
    max_y = st.sidebar.number_input("أعلى خط عرض (Max Latitude):", value=14.5)

# ==========================================
# 2. دالة جلب البيانات عبر WMS (سريعة وخفيفة)
# ==========================================
def fetch_emag2_wms(min_x, max_x, min_y, max_y, is_utm, utm_epsg):
    if is_utm:
        transformer = Transformer.from_crs(f"epsg:{utm_epsg}", "epsg:4326", always_xy=True)
        lon_min, lat_min = transformer.transform(min_x, min_y)
        lon_max, lat_max = transformer.transform(max_x, max_y)
    else:
        lon_min, lon_max, lat_min, lat_max = min_x, max_x, min_y, max_y

    wcs_url = (
        f"https://www.ngdc.noaa.gov/geoserver/wms?"
        f"service=WMS&version=1.1.0&request=GetMap&"
        f"layers=EMAG2_V2&bbox={lon_min},{lat_min},{lon_max},{lat_max}&"
        f"width=300&height=300&srs=EPSG:4326&format=image/geotiff"
    )
    
    with rasterio.open(wcs_url) as src:
        mag_grid = src.read(1)
        
    return mag_grid, lon_min, lon_max, lat_min, lat_max

# ==========================================
# 3. دالة معالجة التراكيب والإشارة التحليلية
# ==========================================
def process_mag(mag_data, dx=2000):
    ny, nx = mag_data.shape
    kx = 2 * np.pi * np.fft.fftfreq(nx, d=dx)
    ky = 2 * np.pi * np.fft.fftfreq(ny, d=dx)
    KX, KY = np.meshgrid(kx, ky)
    K = np.sqrt(KX**2 + KY**2)

    data_ft = fft2(mag_data)

    # المشتقة الرأسية الأولى (FVD)
    fvd = np.real(ifft2(data_ft * K))

    # المشتقات الأفقية والإشارة التحليلية (Analytic Signal)
    dx_map = np.real(ifft2(data_ft * (1j * KX)))
    dy_map = np.real(ifft2(data_ft * (1j * KY)))
    analytic_signal = np.sqrt(dx_map**2 + dy_map**2 + fvd**2)

    return fvd, analytic_signal

# ==========================================
# 4. تنفيذ العمليات عند الضغط على الزر
# ==========================================
if st.button("🚀 جلب البيانات ومعالجة صخور القاعدة"):
    with st.spinner("جاري جلب البيانات المعالجة عبر NOAA WMS..."):
        try:
            is_utm = (coord_type == "UTM")
            mag_grid, lon_min, lon_max, lat_min, lat_max = fetch_emag2_wms(
                min_x, max_x, min_y, max_y, is_utm, epsg
            )
            
            fvd, as_map = process_mag(mag_grid)

            st.success("تم جلب ومعالجة البيانات بنجاح!")

            # عرض النتائج في ألسنة تبويب
            tab1, tab2, tab3 = st.tabs(["الشذوذ المغناطيسي (TMI)", "المشتقة الرأسية (FVD)", "الإشارة التحليلية (Analytic Signal)"])
            
            with tab1:
                st.subheader("خريطة الشذوذ المغناطيسي الكلي (TMI)")
                st.image(mag_grid, use_column_width=True, clamp=True)
            
            with tab2:
                st.subheader("المشتقة الرأسية الأولى (FVD) - لإبراز التراكيب")
                st.image(fvd, use_column_width=True, clamp=True)
                
            with tab3:
                st.subheader("الإشارة التحليلية (Analytic Signal) - لتحديد حدود صخور القاعدة")
                st.image(as_map, use_column_width=True, clamp=True)

            # إعداد ملف Excel للتنزيل
            lons = np.linspace(lon_min, lon_max, mag_grid.shape[1])
            lats = np.linspace(lat_min, lat_max, mag_grid.shape[0])
            lon_g, lat_g = np.meshgrid(lons, lats)
            
            df = pd.DataFrame({
                'Longitude': lon_g.flatten(),
                'Latitude': lat_g.flatten(),
                'TMI_nT': mag_grid.flatten(),
                'Analytic_Signal': as_map.flatten()
            })
            
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 تحميل البيانات بصيغة Excel",
                data=buffer.getvalue(),
                file_name="magnetic_subsurface_data.xlsx",
                mime="application/vnd.ms-excel"
            )

        except Exception as e:
            st.error(f"حدث خطأ أثناء جلب البيانات: {str(e)}")
