import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from pystac_client import Client
import planetary_computer
import rasterio

st.set_page_config(page_title="SanbGeo - Real Global Mineral Exploration Engine", layout="wide")

st.title("🛰️ المنظومة الجيولوجية الحقيقية للاستشعار عن بعد (Global STAC Engine)")
st.markdown("استعلام حقيقي مباشر عن أي إحداثيات في العالم عبر أحدث صور الأقمار الصناعية (Sentinel-2 L2A) واستخراج الشذوذ الطيفي الفعلي.")

st.sidebar.header("📍 إحداثيات منطقة البحث (AOI)")
lat = st.sidebar.number_input("خط العرض (Latitude)", value=29.8500, format="%.4f")
lon = st.sidebar.number_input("خط الطول (Longitude)", value=90.7500, format="%.4f")
buffer_deg = 0.08

st.sidebar.divider()
st.sidebar.header("⚙️ إعدادات البحث الفضائي")
cloud_max = st.sidebar.slider("أقصى نسبة غيوم مسموحة (%)", min_value=10, max_value=100, value=50)
analysis_mode = st.sidebar.selectbox(
    "اختر مؤشر التحليل الطيفي:",
    [
        "مؤشر أكاسيد الحديد الحقيقي (B11 / B04)",
        "مؤشر معادن الطين الحقيقي (B11 / B08)"
    ]
)

if st.button("🌐 جلب وتحليل البيانات الحقيقية للموقع"):
    with st.spinner("جاري الاتصال بقاعدة بيانات الأقمار الصناعية العالمية والبحث عن مشهد حقيقي..."):
        try:
            # الاتصال بمرصد مايكروسوفت للبيانات المكانية (STAC API)
            catalog = Client.open("https://planetarycomputer.microsoft.com/stac", modifier=planetary_computer.sign_inplace)
            bbox = [lon - buffer_deg, lat - buffer_deg, lon + buffer_deg, lat + buffer_deg]
            
            search = catalog.search(
                collections=["sentinel-2-l2a"],
                bbox=bbox,
                datetime="2023-01-01/2026-10-24",
                max_items=3,
                query={"eo:cloud_cover": {"lt": cloud_max}}
            )
            
            items = list(search.items())
            
            if len(items) == 0:
                st.error("❌ لم يتم العثور على أي مشهد فضائي حقيقي مطابق في هذه الإحداثيات (قد تكون المنطقة مغطاة بالغيوم أو خارج نطاق التغطية الحديثة). جرب إحداثيات أخرى لمناطق مكشوفة.")
            else:
                item = items[0]
                st.success(f"✅ تم العثور على مشهد فضائي حقيقي بتاريخ: {item.datetime.strftime('%Y-%m-%d')}")
                
                # جلب النطاقات الحقيقية للأقمار الصناعية
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
                
                # معالجة القيم الصفرية لتجنب أخطاء القسمة
                b4 = np.where(b4 <= 0, 0.001, b4)
                b8 = np.where(b8 <= 0, 0.001, b8)
                
                # تطبيع الصورة المرئية RGB لتظهر التضاريس الطبيعية بدقة
                def norm(band):
                    p2, p98 = np.percentile(band, (2, 98))
                    return np.clip((band - p2) / (p98 - p2 + 1e-5), 0, 1)
                
                rgb_bg = np.dstack((norm(b4), norm(b3), norm(b2)))
                
                # حساب الشذوذ الحقيقي بناءً على البكسلات الفعلية للقمر الصناعي
                if "أكاسيد الحديد" in analysis_mode:
                    anomaly_matrix = b11 / b4
                    cmap_choice = 'hot'
                    title_text = "خريطة الشذوذ الطيفي الحقيقي لأكاسيد الحديد (B11/B04)"
                else:
                    anomaly_matrix = b11 / b8
                    cmap_choice = 'plasma'
                    title_text = "خريطة الشذوذ الطيفي الحقيقي لمعادن الطين (B11/B08)"

                # العرض المرئي للنتائج الحقيقية فقط
                st.markdown("---")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("🌍 الصورة الجوية الحقيقية (True Color)")
                    fig1, ax1 = plt.subplots(figsize=(6, 5))
                    ax1.imshow(rgb_bg)
                    ax1.set_title("صورة الأقمار الصناعية لسطح الأرض")
                    ax1.axis('off')
                    st.pyplot(fig1)
                    
                with col2:
                    st.subheader("🎯 خريطة الشذوذ الطيفي الحقيقي")
                    fig2, ax2 = plt.subplots(figsize=(6, 5))
                    im2 = ax2.imshow(anomaly_matrix, cmap=cmap_choice)
                    ax2.set_title(title_text)
                    fig2.colorbar(im2, ax=ax2)
                    ax2.axis('off')
                    st.pyplot(fig2)
                
                st.success("🎉 تمت معالجة البيانات الفضائية الحقيقية واستخراج النتائج الجيولوجية الفعلية بنجاح تام!")

        except Exception as e:
            st.error(f"⚠️ حدث خطأ تقني أثناء الاتصال بالخادم السحابي: {e}")

else:
    st.warning("⚠️ أدخل إحداثيات أي منطقة في العالم في القائمة الجانبية ثم اضغط على زر الجلب والتحليل الحقيقي.")
