import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from pystac_client import Client
import planetary_computer
import rasterio

st.set_page_config(page_title="SanbGeo - Scientific Spectral Processing Engine", layout="wide")

st.title("🛰️ المنظومة الجيولوجية العلمية: معالجة الأطياف وتحليل الشذوذ الحقيقي")
st.markdown("استخلاص النطاقات الطيفية الفعلية (مرئي، NIR، SWIR) وتطبيق المعادلات الرياضية الجيولوجية لاستكشاف القواطع والشذوذ.")

# لوحة التحكم الجانبية للإحداثيات والمعادلات
st.sidebar.header("📍 إحداثيات موقع الاهتمام (AOI)")
lat = st.sidebar.number_input("خط العرض (Latitude)", value=29.8500, format="%.4f")
lon = st.sidebar.number_input("خط الطول (Longitude)", value=90.7500, format="%.4f")
buffer_deg = 0.08

st.sidebar.divider()
st.sidebar.header("⚙️ إعدادات المعالجة الطيفية")
equation_mode = st.sidebar.selectbox(
    "اختر المعادلة العلمية للتحليل والاستكشاف:",
    [
        "مؤشر أكاسيد الحديد: SWIR1 / Red (كشف التعرية والقواطع)",
        "مؤشر معادن الطين: SWIR1 / NIR (كشف التحول الحراري)",
        "مؤشر السيليكا الهيكلي: (NIR * SWIR1) / Red (كشف العروق والتراكيب)"
    ]
)

if st.button("🔬 تنفيذ المعالجة الطيفية وفق المعادلات الرياضية"):
    with st.spinner("جاري الاتصال السحابي، سحب النطاقات الطيفية الحقيقية، وتطبيق المعادلات الرياضية..."):
        try:
            # 1. الاتصال بمرصد البيانات الفضائية (Sentinel-2 L2A)
            catalog = Client.open("https://planetarycomputer.microsoft.com/stac", modifier=planetary_computer.sign_inplace)
            bbox = [lon - buffer_deg, lat - buffer_deg, lon + buffer_deg, lat + buffer_deg]
            
            search = catalog.search(
                collections=["sentinel-2-l2a"],
                bbox=bbox,
                datetime="2023-01-01/2026-10-24",
                max_items=3,
                query={"eo:cloud_cover": {"lt": 50}}
            )
            items = list(search.items())
            
            if len(items) == 0:
                st.error("❌ لم يتم العثور على مشهد فضائي مغطى بالغيوم المقبولة في هذه الإحداثيات. جرب إحداثيات يابسة مكشوفة.")
            else:
                item = items[0]
                st.success(f"✅ تم سحب المشهد الفضائي بنجاح بتاريخ: {item.datetime.strftime('%Y-%m-%d')}")
                
                # 2. جلب النطاقات الطيفية الحقيقية (Red: B04, NIR: B08, SWIR1: B11, المرئية RGB: B02, B03, B04)
                b2_url = planetary_computer.sign(item.assets["B02"].href)
                b3_url = planetary_computer.sign(item.assets["B03"].href)
                b4_url = planetary_computer.sign(item.assets["B04"].href)
                b8_url = planetary_computer.sign(item.assets["B08"].href)
                b11_url = planetary_computer.sign(item.assets["B11"].href)
                
                win = rasterio.windows.Window(100, 100, 450, 450)
                with rasterio.open(b2_url) as src: b2 = src.read(1, window=win).astype(np.float32)
                with rasterio.open(b3_url) as src: b3 = src.read(1, window=win).astype(np.float32)
                with rasterio.open(b4_url) as src: b4 = src.read(1, window=win).astype(np.float32)
                with rasterio.open(b8_url) as src: b8 = src.read(1, window=win).astype(np.float32)
                with rasterio.open(b11_url) as src: b11 = src.read(1, window=win).astype(np.float32)
                
                # معالجة القيم لتفادي القسمة على الصفر
                b4 = np.where(b4 <= 0, 0.001, b4)
                b8 = np.where(b8 <= 0, 0.001, b8)
                
                # تطبيع النطاقات البصرية لصورة RGB طبيعية واقعية
                def norm(band):
                    p2, p98 = np.percentile(band, (2, 98))
                    return np.clip((band - p2) / (p98 - p2 + 1e-5), 0, 1)
                
                rgb_true = np.dstack((norm(b4), norm(b3), norm(b2)))
                
                # 3. تطبيق المعادلة الرياضية العلمية المختارة بدقة
                if "أكاسيد الحديد" in equation_mode:
                    result_matrix = b11 / b4
                    map_title = "مخرجات معادلة أكاسيد الحديد (SWIR1 / Red)"
                    cmap_name = 'hot'
                elif "معادن الطين" in equation_mode:
                    result_matrix = b11 / b8
                    map_title = "مخرجات معادلة معادن الطين (SWIR1 / NIR)"
                    cmap_name = 'plasma'
                else:
                    result_matrix = (b8 * b11) / b4
                    map_title = "مخرجات مؤشر السيليكا والهياكل (NIR * SWIR1 / Red)"
                    cmap_name = 'inferno'
                
                # تطبيق معالجة تباين إحصائية (Contrast Enhancement) لإبراز التدرجات الحقيقية والشذوذ الفعلي
                p_min, p_max = np.percentile(result_matrix, (5, 95))
                enhanced_anomaly = np.clip((result_matrix - p_min) / (p_max - p_min + 1e-5), 0, 1)

                # 4. العرض المرئي للنتائج العلمية
                st.markdown("---")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("🌍 1. الطيف المرئي الحقيقي (True Color RGB)")
                    fig1, ax1 = plt.subplots(figsize=(6, 5))
                    ax1.imshow(rgb_true)
                    ax1.set_title("صورة الأقمار الصناعية البصرية")
                    ax1.axis('off')
                    st.pyplot(fig1)
                    
                with col2:
                    st.subheader("🎯 2. مخرجات النافذة الطيفية المعالجة")
                    fig2, ax2 = plt.subplots(figsize=(6, 5))
                    im2 = ax2.imshow(enhanced_anomaly, cmap=cmap_name)
                    ax2.set_title(map_title)
                    fig2.colorbar(im2, ax=ax2)
                    ax2.axis('off')
                    st.pyplot(fig2)
                
                st.success("🎉 تمت معالجة النطاقات الطيفية واستخراج النتائج وفق المعادلات الرياضية العلمية بنجاح!")

        except Exception as e:
            st.error(f"⚠️ حدث خطأ أثناء الاتصال أو المعالجة الرياضية: {e}")

else:
    st.warning("⚠️ أدخل الإحداثيات واختر المعادلة العلمية من القائمة الجانبية ثم اضغط على زر التنفيذ للبدء.")
