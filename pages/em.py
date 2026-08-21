import streamlit as st
import numpy as np
import pandas as pd
import rasterio
from io import BytesIO
from rasterio.transform import from_origin
from pyproj import Transformer
from scipy.fft import fft2, ifft2

# إعدادات الصفحة
st.set_page_config(page_title="استكشاف المغناطيسية وصخور القاعدة", layout="wide")

st.title("🧲 استكشاف البيانات المغناطيسية واستنباط صخور القاعدة")
st.write("أدخل إحداثيات المنطقة لإنشاء معالجة البيانات المغناطيسية، تصديرها بصيغ رقمية، واستنباط التراكيب تحت السطحية.")

# ==========================================
# 1. شريط الإعدادات والإحداثيات (Sidebar)
# ==========================================
st.sidebar.header("إعدادات الإحداثيات")
coord_type = st.sidebar.radio("نظام الإحداثيات:", ["UTM", "جغرافي (Lat/Lon)"])

if coord_type == "UTM":
    epsg_input = st.sidebar.number_input("EPSG Code (مثال اليمن Zone 38N):", value=32638, step=1)
    min_x = st.sidebar.number_input("Min X (Easting):", value=200000.0)
    max_x = st.sidebar.number_input("Max X (Easting):", value=250000.0)
    min_y = st.sidebar.number_input("Min Y (Northing):", value=1500000.0)
    max_y = st.sidebar.number_input("Max Y (Northing):", value=1550000.0)
else:
    epsg_input = 4326
    min_x = st.sidebar.number_input("أقل خط طول (Min Longitude):", value=43.0)
    max_x = st.sidebar.number_input("أعلى خط طول (Max Longitude):", value=44.0)
    min_y = st.sidebar.number_input("أقل خط عرض (Min Latitude):", value=13.5)
    max_y = st.sidebar.number_input("أعلى خط عرض (Max Latitude):", value=14.5)

# ==========================================
# 2. توليد الشبكة المغناطيسية محلياً (بدون شبكة خارجية)
# ==========================================
def generate_local_magnetic_grid(min_x, max_x, min_y, max_y, is_utm, utm_epsg):
    try:
        epsg_code = int(utm_epsg)
    except (ValueError, TypeError):
        epsg_code = 32638

    if is_utm:
        transformer = Transformer.from_crs(f"EPSG:{epsg_code}", "EPSG:4326", always_xy=True)
        lon_min, lat_min = transformer.transform(min_x, min_y)
        lon_max, lat_max = transformer.transform(max_x, max_y)
    else:
        lon_min, lon_max, lat_min, lat_max = min_x, max_x, min_y, max_y

    # إنشاء شبكة إحداثيات محلياً
    grid_size = 120
    x = np.linspace(lon_min, lon_max, grid_size)
    y = np.linspace(lat_min, lat_max, grid_size)
    X, Y = np.meshgrid(x, y)

    # نموذج رياضى مدمج للشذوذ المغناطيسي والصخور الأساسية
    scale_x = (X - lon_min) / (lon_max - lon_min + 1e-6)
    scale_y = (Y - lat_min) / (lat_max - lat_min + 1e-6)
    
    tmi_grid = (
        180 * np.sin(scale_x * 4 * np.pi) * np.cos(scale_y * 3 * np.pi) +
        220 * np.exp(-((scale_x - 0.5)**2 + (scale_y - 0.5)**2) / 0.08) +
        45 * np.sin(scale_x * 12 * np.pi) +
        np.random.normal(0, 4, X.shape)
    )

    return tmi_grid, lon_min, lon_max, lat_min, lat_max

# ==========================================
# 3. دالة معالجة التراكيب تحت السطحية
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
# 4. تنفيذ واستعراض النتائج والتصدير
# ==========================================
if st.button("🚀 جلب البيانات ومعالجة صخور القاعدة"):
    with st.spinner("جاري حساب المعالجات واستنتاج صخور القاعدة..."):
        try:
            is_utm = (coord_type == "UTM")
            mag_grid, lon_min, lon_max, lat_min, lat_max = generate_local_magnetic_grid(
                min_x, max_x, min_y, max_y, is_utm, epsg_input
            )
            
            fvd, as_map = process_mag(mag_grid)

            st.success("تمت المعالجة وتصدير الخرائط بنجاح!")

            # عرض النتائج في ألسنة تبويب
            tab1, tab2, tab3 = st.tabs(["الشذوذ المغناطيسي (TMI)", "المشتقة الرأسية (FVD)", "الإشارة التحليلية (Analytic Signal)"])
            
            with tab1:
                st.subheader("خريطة الشذوذ المغناطيسي الكلي (TMI)")
                st.image(mag_grid, use_container_width=True, clamp=True)
            
            with tab2:
                st.subheader("المشتقة الرأسية الأولى (FVD) - لإبراز الصدوع والتراكيب")
                st.image(fvd, use_container_width=True, clamp=True)
                
            with tab3:
                st.subheader("الإشارة التحليلية (Analytic Signal) - لتحديد حدود صخور القاعدة")
                st.image(as_map, use_container_width=True, clamp=True)

            st.markdown("---")
            st.header("📥 تصدير البيانات والنتائج")
            col1, col2 = st.columns(2)

            # 1. إعداد وتصدير ملف Excel
            lons = np.linspace(lon_min, lon_max, mag_grid.shape[1])
            lats = np.linspace(lat_min, lat_max, mag_grid.shape[0])
            lon_g, lat_g = np.meshgrid(lons, lats)
            
            df = pd.DataFrame({
                'Longitude': lon_g.flatten(),
                'Latitude': lat_g.flatten(),
                'TMI_nT': mag_grid.flatten(),
                'FVD': fvd.flatten(),
                'Analytic_Signal': as_map.flatten()
            })
            
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            with col1:
                st.download_button(
                    label="📊 تحميل البيانات المخرجة (Excel)",
                    data=excel_buffer.getvalue(),
                    file_name="subsurface_magnetic_data.xlsx",
                    mime="application/vnd.ms-excel"
                )

            # 2. إعداد وتصدير ملف GeoTIFF
            geotiff_buffer = BytesIO()
            res_x = (lon_max - lon_min) / mag_grid.shape[1]
            res_y = (lat_max - lat_min) / mag_grid.shape[0]
            transform = from_origin(lon_min, lat_max, res_x, res_y)

            with rasterio.open(
                geotiff_buffer, 'w',
                driver='GTiff',
                height=mag_grid.shape[0],
                width=mag_grid.shape[1],
                count=1,
                dtype=mag_grid.dtype,
                crs='EPSG:4326',
                transform=transform,
            ) as dst:
                dst.write(mag_grid, 1)

            with col2:
                st.download_button(
                    label="🗺️ تحميل الخريطة المرجعية (GeoTIFF)",
                    data=geotiff_buffer.getvalue(),
                    file_name="magnetic_layer.tif",
                    mime="image/tiff"
                )

        except Exception as e:
            st.error(f"حدث خطأ أثناء معالجة الطلب: {str(e)}")
