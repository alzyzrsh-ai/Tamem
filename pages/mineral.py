import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from pystac_client import Client
import planetary_computer
import rasterio

st.set_page_config(page_title="SanbGeo - True Color & Mineral Engine", layout="wide")

st.title("🛰️ نظام الاستشعار الحقيقي: الصورة الجوية الطبيعية وتحليل الأطياف")
st.markdown("عرض الصورة الفضائية الحقيقية بالألوان الطبيعية (True Color RGB) مع استكشاف التمعدن السطحي.")

# لوحة التحكم الجانبية لإدخال الإحداثيات
st.sidebar.header("📍 إحداثيات منطقة الاهتمام (AOI)")
lat = st.sidebar.number_input("خط العرض (Latitude)", value=15.3694, format="%.4f")
lon = st.sidebar.number_input("خط الطول (Longitude)", value=44.1910, format="%.4f")
buffer_deg = 0.08

st.sidebar.divider()
st.sidebar.header("⚙️ إعدادات البحث والتحليل الطيفي")
cloud_max = st.sidebar.slider("أقصى نسبة غيوم مسموحة (%)", min_value=10, max_value=100, value=60)
analysis_mode = st.sidebar.selectbox(
    "اختر نوع التحليل الاستكشافي:",
    [
        "مؤشر أكاسيد الحديد الحقيقي (B11 / B04)",
        "مؤشر معادن الطين الحقيقي (B11 / B08)"
    ]
)

if st.button("🌐 جلب الصورة الجوية الحقيقية ومعالجة الأطياف"):
    with st.spinner("جاري الاتصال بمرصد الأقمار الصناعية وسحب الصورة الجوية والنطاقات الطيفية..."):
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
                st.error("❌ لم يتم العثور على مشهد فضائي مطابق. جرب زيادة 'أقصى نسبة غيوم مسموحة' من القائمة الجانبية أو تغيير الإحداثيات قليلاً.")
            else:
                item = items[0]
                st.success(f"✅ تم بنجاح جلب المشهد الفضائي بتاريخ: {item.datetime.strftime('%Y-%m-%d')}")
                
                # جلب نطاقات الصورة الحقيقية بالألوان الطبيعية (Red: B04, Green: B03, Blue: B02) والنطاقات الاستكشافية (NIR: B08, SWIR: B11)
                red_url = planetary_computer.sign(item.assets["B04"].href)
                green_url = planetary_computer.sign(item.assets["B03"].href)
                blue_url = planetary_computer.sign(item.assets["B02"].href)
                nir_url = planetary_computer.sign(item.assets["B08"].href)
                swir_url = planetary_computer.sign(item.assets["B11"].href)
                
                win = rasterio.windows.Window(150, 150, 450, 450)
                
                with rasterio.open(red_url) as src: r = src.read(1, window=win).astype(np.float32)
                with rasterio.open(green_url) as src: g = src.read(1, window=win).astype(np.float32)
                with rasterio.open(blue_url) as src: b = src.read(1, window=win).astype(np.float32)
                with rasterio.open(nir_url) as src: nir = src.read(1, window=win).astype(np.float32)
                with rasterio.open(swir_url) as src: swir = src.read(1, window=win).astype(np.float32)
                
                # تطبيع (Normalization) الصورة الملونة RGB لتظهر بوضوح فائق وعين بشرية واقعية
                def normalize_img(band):
                    p_min, p_max = np.percentile(band, (2, 98))
                    norm = np.clip((band - p_min) / (p_max - p_min + 1e-5), 0, 1)
                    return norm

                rgb_stacked = np.dstack((normalize_img(r), normalize_img(g), normalize_img(b)))
                
                # تجنب القسمة على الصفر
                r = np.where(r == 0, 0.001, r)
                nir = np.where(nir == 0, 0.001, nir)
                
                # 3. حساب خوارزمية الباند ريشيو
                if "أكاسيد الحديد" in analysis_mode:
                    result_matrix = swir / r
                    color_map = 'hot'
                    title_text = "خريطة الشذوذ الطيفي لأكاسيد الحديد (Iron Oxides)"
                else:
                    result_matrix = swir / nir
                    color_map = 'plasma'
                    title_text = "خريطة معادن الطين والهيدروكسيل (Clays)"

                # 4. العرض المرئي للنتائج جنباً إلى جنب أو متسلسلاً
                st.markdown("---")
                st.subheader("🌍 أولاً: الصورة الجوية الحقيقية لسطح الأرض (True Color RGB)")
                st.markdown("تتيح لك هذه الصورة معاينة التضاريس الحقيقية وملاحظة أي سحب أو غيوم بشكل مباشر.")
                fig1, ax1 = plt.subplots(figsize=(7, 5))
                ax1.imshow(rgb_stacked)
                ax1.set_title("صورة الأقمار الصناعية الطبيعية (Sentinel-2 RGB)")
                ax1.axis('off')
                st.pyplot(fig1)
                
                st.markdown("---")
                st.subheader("🎯 ثانياً: مخرجات التحليل الاستكشافي وشذوذ التمعدن")
                fig2, ax2 = plt.subplots(figsize=(7, 5))
                im2 = ax2.imshow(result_matrix, cmap=color_map)
                ax2.set_title(title_text)
                fig2.colorbar(im2, ax=ax2)
                ax2.axis('off')
                st.pyplot(fig2)
                
                st.success("🎉 تمت المعالجة البصرية والمكانية بنجاح تام!")

        except Exception as e:
            st.error(f"⚠️ حدث خطأ أثناء جلب البيانات: {e}")

else:
    st.warning("⚠️ أدخل إحداثيات موقعك في القائمة الجانبية ثم اضغط على زر الجلب لعرض الصورة الجوية الحقيقية والتحليل.")
