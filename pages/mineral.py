import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from pystac_client import Client
import planetary_computer
import rasterio

st.set_page_config(page_title="SanbGeo - True Satellite Engine", layout="wide")

st.title("🛰️ نظام الاستشعار الفضائي الحقيقي (Direct STAC Engine)")
st.markdown("الاتصال المباشر بقواعد بيانات الأقمار الصناعية (Sentinel-2 L2A) وسحب النطاقات الطيفية الحقيقية معالجّة جغرافياً.")

# لوحة التحكم الجانبية لإدخال الإحداثيات
st.sidebar.header("📍 إحداثيات منطقة الاهتمام (AOI)")
lat = st.sidebar.number_input("خط العرض (Latitude)", value=15.3694, format="%.4f")
lon = st.sidebar.number_input("خط الطول (Longitude)", value=44.1910, format="%.4f")
# توسيع نطاق البحث قليلاً لضمان التقاط المشهد الفضائي بدقة
buffer_deg = 0.1 

st.sidebar.divider()
st.sidebar.header("⚙️ إعدادات التحليل الطيفي")
cloud_max = st.sidebar.slider("أقصى نسبة غيوم مسموحة (%)", min_value=10, max_value=100, value=70)
analysis_mode = st.sidebar.selectbox(
    "اختر نوع التحليل الاستكشافي:",
    [
        "مؤشر أكاسيد الحديد الحقيقي (B11 / B04)",
        "مؤشر معادن الطين الحقيقي (B11 / B08)"
    ]
)

if st.button("🌐 جلب البيانات الحقيقية ومعالجة الأطياف"):
    with st.spinner("جاري الاتصال المباشر بمرصد الأقمار الصناعية وسحب نطاقات السطح الحقيقية..."):
        try:
            # 1. الاتصال بمرصد مايكروسوفت للبيانات المكانية
            catalog = Client.open("https://planetarycomputer.microsoft.com/stac", modifier=planetary_computer.sign_inplace)
            bbox = [lon - buffer_deg, lat - buffer_deg, lon + buffer_deg, lat + buffer_deg]
            
            # 2. البحث عن المشهد الفضائي
            search = catalog.search(
                collections=["sentinel-2-l2a"],
                bbox=bbox,
                datetime="2023-01-01/2026-10-24",
                max_items=5,
                query={"eo:cloud_cover": {"lt": cloud_max}}
            )
            
            items = list(search.items())
            
            if len(items) == 0:
                st.error("❌ لم يتم العثور على مشاهد فضائية مطابقة للإحداثيات الحالية. جرب زيادة نسبة الغيوم أو تغيير الإحداثيات إلى منطقة أخرى (مثل صحراء أو منطقة مكشوفة).")
            else:
                # أخذ أحدث مشهد متاح
                item = items[0]
                st.success(f"✅ تم الاتصال بنجاح وجلب مشهد فضائي حقيقي بتاريخ: {item.datetime.strftime('%Y-%m-%d')}")
                
                # استخدام الأسماء المعيارية المباشرة لنطاقات Sentinel-2 في Planetary Computer
                red_url = planetary_computer.sign(item.assets["B04"].href)
                nir_url = planetary_computer.sign(item.assets["B08"].href)
                swir_url = planetary_computer.sign(item.assets["B11"].href)
                
                # قراءة نافذة مكانية من الصور الحقيقية عبر Rasterio
                with rasterio.open(red_url) as src_red:
                    red_band = src_red.read(1, window=rasterio.windows.Window(200, 200, 500, 500)).astype(np.float32)
                with rasterio.open(nir_url) as src_nir:
                    nir_band = src_nir.read(1, window=rasterio.windows.Window(200, 200, 500, 500)).astype(np.float32)
                with rasterio.open(swir_url) as src_swir:
                    swir_band = src_swir.read(1, window=rasterio.windows.Window(200, 200, 500, 500)).astype(np.float32)
                
                # تجنب القسمة على الصفر
                red_band = np.where(red_band == 0, 0.001, red_band)
                nir_band = np.where(nir_band == 0, 0.001, nir_band)
                
                # 3. حساب خوارزمية الباند ريشيو الحقيقية
                if "أكاسيد الحديد" in analysis_mode:
                    result_matrix = swir_band / red_band
                    color_map = 'hot'
                    title_text = "خريطة الشذوذ الطيفي الحقيقي لأكاسيد الحديد (Sentinel-2 L2A)"
                else:
                    result_matrix = swir_band / nir_band
                    color_map = 'plasma'
                    title_text = "خريطة معادن الطين الحقيقية والهيدروكسيل (Sentinel-2 L2A)"

                # 4. العرض المرئي للنتائج الحقيقية
                st.markdown("---")
                st.subheader("📷 أولاً: النطاق البصري الحقيقي لسطح الأرض (B04)")
                fig1, ax1 = plt.subplots(figsize=(8, 4.5))
                im1 = ax1.imshow(red_band, cmap='gray')
                ax1.set_title("صورة القمر الصناعي الأصلية للموقع")
                fig1.colorbar(im1, ax=ax1)
                st.pyplot(fig1)
                
                st.markdown("---")
                st.subheader("🎯 ثانياً: خريطة الشذوذ التمعدني الحقيقي المستخرجة من الأقمار الصناعية")
                fig2, ax2 = plt.subplots(figsize=(8, 4.5))
                im2 = ax2.imshow(result_matrix, cmap=color_map)
                ax2.set_title(title_text)
                fig2.colorbar(im2, ax=ax2)
                st.pyplot(fig2)
                
                st.success("🎉 تمت معالجة النطاقات الطيفية الحقيقية واستخراج أهداف الاستكشاف بنجاح ت تام!")

        except Exception as e:
            st.error(f"⚠️ حدث خطأ تقني أثناء الاتصال السحابي: {e}")

else:
    st.warning("⚠️ أدخل إحداثيات موقعك في القائمة الجانبية ثم اضغط على زر الجلب الحقيقي للبدء.")
