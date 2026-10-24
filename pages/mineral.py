import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from pystac_client import Client
import planetary_computer
import rasterio

st.set_page_config(page_title="SanbGeo - Advanced Mineral Exploration Engine", layout="wide")

st.title("🛰️ المنظومة الجيولوجية المتقدمة: تصنيف نطاقات التحول والتمعدن السطحي")
st.markdown("استخلاص وتصنيف نطاقات الشذوذ المعدني (أكاسيد الحديد، الطين، البوتاسيوم، والسيليكا) دمجاً مع الصور الجوية الحقيقية.")

# لوحة التحكم الجانبية للإحداثيات ومنطقة الاهتمام
st.sidebar.header("📍 إحداثيات منطقة البحث (AOI)")
# إحداثيات افتراضية لمنطقة غنية بالتراكيب أو يمكنك إدخال إحداثياتك بدقة
lat = st.sidebar.number_input("خط العرض (Latitude)", value=29.8500, format="%.4f")
lon = st.sidebar.number_input("خط الطول (Longitude)", value=90.7500, format="%.4f")
buffer_deg = 0.08

st.sidebar.divider()
st.sidebar.header("⚙️ إعدادات العرض التصنيفي")
cloud_max = st.sidebar.slider("أقصى نسبة غيوم مسموحة (%)", min_value=10, max_value=100, value=50)

if st.button("🚀 تنفيذ المعالجة الطيفية الشاملة وتوليد الخريطة التصنيفية"):
    with st.spinner("جاري الاتصال السحابي بمرصد الأقمار الصناعية وسحب النطاقات المتعددة..."):
        try:
            # 1. الاتصال بمرصد مايكروسوفت للبيانات المكانية (STAC API)
            catalog = Client.open("https://planetarycomputer.microsoft.com/stac", modifier=planetary_computer.sign_inplace)
            bbox = [lon - buffer_deg, lat - buffer_deg, lon + buffer_deg, lat + buffer_deg]
            
            search = catalog.search(
                collections=["sentinel-2-l2a"],
                bbox=bbox,
                datetime="2023-01-01/2026-10-24",
                max_items=5,
                query={"eo:cloud_cover": {"lt": cloud_max}}
            )
            
            items = list(search.items())
            
            if len(items) == 0:
                st.error("❌ لم يتم العثور على مشهد فضائي مطابق. جرب زيادة نسبة الغيوم أو تغيير الإحداثيات إلى منطقة أخرى مكشوفة.")
            else:
                item = items[0]
                st.success(f"✅ تم بنجاح جلب المشهد الفضائي الحقيقي بتاريخ: {item.datetime.strftime('%Y-%m-%d')}")
                
                # سحب النطاقات الطيفية الحقيقية (Blue: B02, Green: B03, Red: B04, NIR: B08, SWIR1: B11, SWIR2: B12)
                b2_url = planetary_computer.sign(item.assets["B02"].href)
                b3_url = planetary_computer.sign(item.assets["B03"].href)
                b4_url = planetary_computer.sign(item.assets["B04"].href)
                b8_url = planetary_computer.sign(item.assets["B08"].href)
                b11_url = planetary_computer.sign(item.assets["B11"].href)
                
                win = rasterio.windows.Window(100, 100, 400, 400)
                
                with rasterio.open(b2_url) as src: b2 = src.read(1, window=win).astype(np.float32)
                with rasterio.open(b3_url) as src: b3 = src.read(1, window=win).astype(np.float32)
                with rasterio.open(b4_url) as src: b4 = src.read(1, window=win).astype(np.float32)
                with rasterio.open(b8_url) as src: b8 = src.read(1, window=win).astype(np.float32)
                with rasterio.open(b11_url) as src: b11 = src.read(1, window=win).astype(np.float32)
                
                # تطبيع الصورة لتظهر كخلفية تضاريسية حقيقية RGB
                def norm(band):
                    p2, p98 = np.percentile(band, (2, 98))
                    return np.clip((band - p2) / (p98 - p2 + 1e-5), 0, 1)
                
                rgb_bg = np.dstack((norm(b4), norm(b3), norm(b2)))
                
                # 2. تطبيق خوارزميات عتبات التمعدن المتعددة (Multi-Mineral Thresholding) مطابقة للأبحاث العالمية
                # لتوليد خريطة تصنيفية مشابهة لصورة القولوغ وجياما
                h, w = b4.shape
                classification_map = np.zeros((h, w, 3)) # خريطة ملونة RGB افتراضية للتصنيف
                
                # حساب نسب النطاقات الطيفية للمعادن المستهدفة
                iron_oxide_ratio = b11 / (b4 + 0.001)   # أكاسيد الحديد
                clay_ratio = b11 / (b8 + 0.001)         # معادن الطين والهيدروكسيل
                silica_ratio = (b8 * b11) / (b4 + 0.001)  # السيليكا والتحول
                
                # عتبات التصنيف لتلوين بقع الشذوذ المعدني على خلفية التضاريس
                # الأحمر: أكاسيد الحديد (Iron-stained)
                iron_mask = iron_oxide_ratio > np.percentile(iron_oxide_ratio, 88)
                # الأصفر: معادن الطين (Hydroxylate / Clays)
                clay_mask = clay_ratio > np.percentile(clay_ratio, 90)
                # الأزرق / الأرجواني: السيليكا ومناطق التحول الحراري المائي (Silicification / Sericitization)
                silica_mask = silica_ratio > np.percentile(silica_ratio, 92)
                
                # دمج النتائج في خريطة مرئية احترافية
                display_overlay = rgb_bg.copy()
                display_overlay[iron_mask] = [1.0, 0.0, 0.0]     # تلوين أكاسيد الحديد بالأحمر الفاقع
                display_overlay[clay_mask] = [1.0, 1.0, 0.0]     # تلوين الطين بالأصفر
                display_overlay[silica_mask] = [0.0, 1.0, 1.0]   # تلوين السيليكا بالسيروسيان/الأزرق الفاتح
                
                # 3. العرض المرئي الاحترافي للمخرجات
                st.markdown("---")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("🌍 الصورة الجوية الطبيعية للمنطقة (True Color)")
                    fig1, ax1 = plt.subplots(figsize=(6, 5))
                    ax1.imshow(rgb_bg)
                    ax1.set_title("التضاريس السطحية الأصلية")
                    ax1.axis('off')
                    st.pyplot(fig1)
                    
                with col2:
                    st.subheader("🎯 خريطة الشذوذ التصنيفية للتمعدن (Alteration Map)")
                    fig2, ax2 = plt.subplots(figsize=(6, 5))
                    ax2.imshow(display_overlay)
                    ax2.set_title("خريطة نطاقات الاستكشاف المعدني المدمجة")
                    ax2.axis('off')
                    st.pyplot(fig2)
                
                # جدول مفتاح الخرائط (Legend) مطابق للأسلوب البحثي العالمي
                st.markdown("---")
                st.subheader("📋 دليل مفتاح الخرائط التعدينية (Legend):")
                l_col1, l_col2, l_col3 = st.columns(3)
                with l_col1:
                    st.markdown("🟥 **أكاسيد الحديد (Iron-stained):** تمثل تركزات حديدية سطحية.")
                with l_col2:
                    st.markdown("🟨 **معادن الطين (Hydroxylate):** تشير إلى نطاقات التغير المائي الحراري.")
                with l_col3:
                    st.markdown("🟦 **السيليكا والتحول (Silicification):** تدل على نطاقات السليكا والتمعدن المرافق.")
                
                st.success("🎉 تمت عملية المعالجة الطيفية المتقدمة واستخراج خريطة الاستكشاف بنجاح تام مطابقة للأبحاث العالمية!")

        except Exception as e:
            st.error(f"⚠️ حدث خطأ تقني أثناء المعالجة: {e}")

else:
    st.warning("⚠️ أدخل إحداثيات منطقة البحث في القائمة الجانبية واضغط على زر التنفيذ لتوليد الخريطة الاستكشافية الواقعية.")
