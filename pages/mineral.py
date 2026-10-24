import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from pystac_client import Client
import planetary_computer
-import rioxarray
import rasterio

st.set_page_config(page_title="SanbGeo - Real Satellite Remote Sensing Engine", layout="wide")

st.title("🛰️ نظام الاستشعار الحقيقي: الاتصال بالأقمار الصناعية وتحليل الأطياف")
st.markdown("جلب بيانات الأقمار الصناعية (Sentinel-2) حياً من السحابة بناءً على الإحداثيات الجغرافية وتطبيق مؤشرات التمعدن.")

# لوحة التحكم الجانبية لإدخال الإحداثيات
st.sidebar.header("📍 إحداثيات منطقة الاهتمام (AOI)")
lat = st.sidebar.number_input("خط العرض (Latitude)", value=15.3694, format="%.4f")
lon = st.sidebar.number_input("خط الطول (Longitude)", value=44.1910, format="%.4f")
buffer_deg = 0.05 # نطاق التغطية الجغرافية

st.sidebar.divider()
st.sidebar.header("⚙️ إعدادات التحليل الطيفي")
analysis_mode = st.sidebar.selectbox(
    "اختر نوع التحليل الاستكشافي:",
    [
        "مؤشر أكاسيد الحديد (Iron Oxides - SWIR/Red)",
        "مؤشر معادن الطين والهيدروكسيل (Clay/Hydroxyl - SWIR/NIR)"
    ]
)

if st.button("🌐 جلب بيانات القمر الصناعي الحقيقي والمعالجة"):
    with st.spinner("جاري الاتصال بـ STAC API والبحث عن أحدث صور القمر الصناعي Sentinel-2 للموقع..."):
        try:
        # 1. الاتصال بمرصد البيانات الفضائية (Planetary Computer)
            catalog = Client.open("https://planetarycomputer.microsoft.com/stac", modifier=planetary_computer.sign_inplace)
            
            # تحديد حدود البحث الجغرافي (Bounding Box حول الإحداثيات)
            bbox = [lon - buffer_deg, lat - buffer_deg, lon + buffer_deg, lat + buffer_deg]
            
            # البحث عن مشاهد Sentinel-2 حديثة وخالية من الغيوم
            search = catalog.search(
                collections=["sentinel-2-l2a"],
                bbox=bbox,
                max_items=1,
                query={"eo:cloud_cover": {"lt": 10}}
            )
            
            items = list(search.items())
            
            if len(items) > 0:
                item = items[0]
                st.success(f"تم العثور على مشهد فضائي حقيقي بتاريخ: {item.datetime.strftime('%Y-%m-%d')}!")
                
                # ج روابط النطاقات الحقيقية (Red: B04, NIR: B08, SWIR1: B11)
                red_url = planetary_computer.sign(item.assets["red"].href)
                nir_url = planetary_computer.sign(item.assets["nir"].href)
                swir_url = planetary_computer.sign(item.assets["swir16"].href)
                
                # قراءة نطاق مصغر من الصورة الحقيقية عبر Rasterio
                with rasterio.open(red_url) as src_red:
                    red_band = src_red.read(1, window=rasterio.windows.Window(100, 100, 500, 500)).astype(np.float32)
                with rasterio.open(nir_url) as src_nir:
                    nir_band = src_nir.read(1, window=rasterio.windows.Window(100, 100, 500, 500)).astype(np.float32)
                with rasterio.open(swir_url) as src_swir:
                    swir_band = src_swir.read(1, window=rasterio.windows.Window(100, 100, 500, 500)).astype(np.float32)
                
                # 2. تطبيق خوارزمية الباند ريشيو على البيانات الحقيقية
                if "أكاسيد الحديد" in analysis_mode:
                    result_matrix = swir_band / (red_band + 0.001)
                    color_map = 'hot'
                    title_text = "خريطة الشذوذ الحقيقي لأكاسيد الحديد (Sentinel-2)"
                else:
                    result_matrix = swir_band / (nir_band + 0.001)
                    color_map = 'plasma'
                    title_text = "خريطة معادن الطين الحقيقية (Sentinel-2)"

                # 3. العرض المرئي للنتائج الحقيقية
                st.markdown("---")
                st.subheader("📷 أولاً: النطاق البصري الحقيقي (Red Band)")
                fig1, ax1 = plt.subplots(figsize=(7, 4))
                im1 = ax1.imshow(red_band, cmap='gray')
                ax1.set_title("صورة الأقمار الصناعية الأصلية (سطح الأرض)")
                fig1.colorbar(im1, ax=ax1)
                st.pyplot(fig1)
                
                st.markdown("---")
                st.subheader("🎯 ثانياً: مخرجات التحليل الطيفي الفضائي الحقيقي")
                fig2, ax2 = plt.subplots(figsize=(7, 4))
                im2 = ax2.imshow(result_matrix, cmap=color_map)
                ax2.set_title(title_text)
                fig2.colorbar(im2, ax=ax2)
                st.pyplot(fig2)
                
                st.success("🎉 تم إتمام تحليل البيانات الفضائية الحقيقية بنجاح تام!")
                
            else:
                st.warning("لم يتم العثور على صور حديثة خالية من الغيوم لهذه الإحداثيات، جرب إحداثيات أخرى.")
                
        except Exception as e:
            st.error(f"حدث خطأ أثناء الاتصال بالأقمار الصناعية: {e}")

else:
    st.warning("⚠️ أدخل الإحداثيات المطلوبة في القائمة الجانبية ثم اضغط على زر الجلب والمعالجة الحية.")
