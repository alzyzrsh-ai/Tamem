import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from pystac_client import Client
import planetary_computer
import rasterio

st.set_page_config(page_title="SanbGeo - Smart Global Sentinel Engine", layout="wide")

st.title("🛰️ المنظومة الجيولوجية الذكية للاستشعار عن بعد (Smart STAC Engine)")
st.markdown("محرك بحث سحابي ذكي يتكيف تلقائياً لجلب أحدث بيانات الأقمار الصناعية الحقيقية لأي إحداثيات في العالم.")

# لوحة التحكم الجانبية للإحداثيات مع خيار التحميل السريع لمنطقة تجريبية مضمونة
st.sidebar.header("📍 إحداثيات منطقة البحث (AOI)")

# زر مساعدة لاختيار منطقة تجريبية معروفة بغناها المعدني ومضمونة التغطية
load_preset = st.sidebar.button("🌟 تحميل إحداثيات منطقة تجريبية (قولوغ - التبت)")
if load_preset:
    default_lat, default_lon = 29.8500, 90.7500
else:
    default_lat, default_lon = 15.3694, 44.1910

lat = st.sidebar.number_input("خط العرض (Latitude)", value=default_lat, format="%.4f")
lon = st.sidebar.number_input("خط الطول (Longitude)", value=default_lon, format="%.4f")
buffer_deg = 0.08

st.sidebar.divider()
st.sidebar.header("⚙️ إعدادات التحليل الطيفي")
analysis_mode = st.sidebar.selectbox(
    "اختر مؤشر التحليل الطيفي:",
    [
        "مؤشر أكاسيد الحديد الحقيقي (B11 / B04)",
        "مؤشر معادن الطين الحقيقي (B11 / B08)"
    ]
)

if st.button("🌐 جلب وتحليل البيانات الحقيقية بذكاء"):
    with st.spinner("جاري الاتصال السحابي والبحث الذكي عن أفضل مشهد فضائي متاح للموقع..."):
        try:
            catalog = Client.open("https://planetarycomputer.microsoft.com/stac", modifier=planetary_computer.sign_inplace)
            bbox = [lon - buffer_deg, lat - buffer_deg, lon + buffer_deg, lat + buffer_deg]
            
            # محاولة البحث الأولى (فلتر متقدم حديث)
            search = catalog.search(
                collections=["sentinel-2-l2a"],
                bbox=bbox,
                datetime="2024-01-01/2026-10-24",
                max_items=5,
                query={"eo:cloud_cover": {"lt": 30}}
            )
            items = list(search.items())
            
            # محاولة بحث احتياطية ذكية (توسيع النطاق الزمني وزيادة نسبة الغيوم تلقائياً إذا لمשkد نتائج)
            if len(items) == 0:
                st.info("🔄 جاري توسيع نطاق البحث في الأرشيف السحابي لضمان جلب تغطية للمنطقة...")
                search = catalog.search(
                    collections=["sentinel-2-l2a"],
                    bbox=bbox,
                    datetime="2020-01-01/2026-10-24",
                    max_items=10,
                    query={"eo:cloud_cover": {"lt": 80}}
                )
                items = list(search.items())
            
            if len(items) == 0:
                st.error("❌ عذراً، هذه الإحداثيات تقع في منطقة لا تتوفر لها بيانات تغطية حديثة في الأقمار الصناعية (مثل المحيطات أو مناطق غير مسوحة). جرب إحداثيات اليابسة أو اضغط على زر المنطقة التجريبية في القائمة الجانبية.")
            else:
                # اختيار المشهد الأقل غيوماً ذكياً
                items.sort(key=lambda x: x.properties.get("eo:cloud_cover", 100))
                item = items[0]
                cloud_val = item.properties.get("eo:cloud_cover", 0)
                st.success(f"✅ تم بنجاح العثور على مشهد فضائي حقيقي بتاريخ: {item.datetime.strftime('%Y-%m-%d')} (نسبة الغيوم: {cloud_val:.1f}%)")
                
                # جلب النطاقات الحقيقية
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
                
                b4 = np.where(b4 <= 0, 0.001, b4)
                b8 = np.where(b8 <= 0, 0.001, b8)
                
                def norm(band):
                    p2, p98 = np.percentile(band, (2, 98))
                    return np.clip((band - p2) / (p98 - p2 + 1e-5), 0, 1)
                
                rgb_bg = np.dstack((norm(b4), norm(b3), norm(b2)))
                
                if "أكاسيد الحديد" in analysis_mode:
                    anomaly_matrix = b11 / b4
                    cmap_choice = 'hot'
                    title_text = "خريطة الشذوذ الطيفي الحقيقي لأكاسيد الحديد (B11/B04)"
                else:
                    anomaly_matrix = b11 / b8
                    cmap_choice = 'plasma'
                    title_text = "خريطة الشذوذ الطيفي الحقيقي لمعادن الطين (B11/B08)"

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
    st.warning("⚠️ أدخل إحداثيات موقعك أو اضغط زر المنطقة التجريبية في القائمة الجانبية ثم اضغط زر الجلب والتحليل.")
