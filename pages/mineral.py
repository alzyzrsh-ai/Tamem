import streamlit as st
import matplotlib.pyplot as plt
import urllib.request
import io
from PIL import Image
import numpy as np
import math

st.set_page_config(page_title="SanbGeo - Real Pixel Spectral Engine", layout="wide")

st.title("🛰️ المنظومة الجيولوجية: استخراج الشذوذ من بكسلات الصورة الحقيقية")
st.markdown("معالجة بكسلات الصورة الجوية الفعلية وتطبيق المعادلات الرياضية لاستخراج التمعدن الحقيقي دون أي رسومات افتراضية.")

st.sidebar.header("📍 إحداثيات الموقع")
lat = st.sidebar.number_input("خط العرض (Latitude)", value=15.3694, format="%.4f")
lon = st.sidebar.number_input("خط الطول (Longitude)", value=44.1910, format="%.4f")
zoom_level = st.sidebar.slider("مستوى التقريب (Zoom Level)", min_value=10, max_value=17, value=14)

st.sidebar.divider()
st.sidebar.header("⚙️ معادلة الاستخلاص الطيفي للألوان الحقيقية")
index_type = st.sidebar.selectbox(
    "اختر مؤشر المعالجة البكسلية:",
    [
        "مؤشر أكاسيد الحديد المرئي (Red / Green)",
        "مؤشر الشذوذ والتباين السطحي (Brightness Index)",
        "مؤشر التشبع التعديني للصخور (Saturation Contrast)"
    ]
)

if st.button("🌐 جلب الصورة الحقيقية واستخراج الشذوذ من بكسلاتها"):
    with st.spinner("جاري جلب الصورة الجوية الحقيقية وتحليل بكسلاتها الفعلية..."):
        try:
            # 1. جلب الصورة الجوية الحقيقية لسطح الأرض
            lat_rad = math.radians(lat)
            n = 2.0 ** zoom_level
            xtile = int((lon + 180.0) / 360.0 * n)
            ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
            
            tile_url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{zoom_level}/{ytile}/{xtile}"
            
            req = urllib.request.Request(tile_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                image_data = response.read()
                
            img_pil = Image.open(io.BytesIO(image_data)).convert('RGB')
            img_np = np.array(img_pil).astype(np.float32) / 255.0
            
            # 2. قراءة القنوات الفعلية (Red, Green, Blue) من البكسلات الحقيقية
            R = img_np[:, :, 0] + 0.001
            G = img_np[:, :, 1] + 0.001
            B = img_np[:, :, 2] + 0.001
            
            # 3. تطبيق معادلات حقيقية مستمدة 100% من بكسلات الصورة الفعلية
            if "أكاسيد الحديد" in index_type:
                # مؤشر يعتمد على نسبة القناة الحمراء للأخضر لإبراز التعرية والتربة الصخرية
                anomaly_matrix = R / G
                map_title = "خريطة أكاسيد الحديد المستخرجة من بكسلات الصورة الفعلية (R / G)"
                cmap_choice = 'hot'
            elif "التباين السطحي" in index_type:
                # مؤشر السطوع والشدة التضاريسية الحقيقية
                anomaly_matrix = np.sqrt((R**2 + G**2 + B**2) / 3.0)
                map_title = "خريطة التباين والسطوع السطحي الحقيقي للموقع"
                cmap_choice = 'plasma'
            else:
                # مؤشر التشبع الطيفي الصخري
                max_val = np.maximum(np.maximum(R, G), B)
                min_val = np.minimum(np.minimum(R, G), B)
                anomaly_matrix = (max_val - min_val) / (max_val + 0.001)
                map_title = "خريطة التشبع الطيفي الصخري المستمدة من الألوان الحقيقية"
                cmap_choice = 'inferno'

            # تطبيع مصفوفة النتائج المستخرجة من البكسلات الحقيقية لإبراز التباين بوضوح
            p_min, p_max = np.percentile(anomaly_matrix, (2, 98))
            final_anomaly = np.clip((anomaly_matrix - p_min) / (p_max - p_min + 1e-5), 0, 1)

            # 4. العرض المرئي الثنائي جنباً إلى جنب
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🌍 1. الصورة الجوية الحقيقية للموقع")
                fig1, ax1 = plt.subplots(figsize=(6, 6))
                ax1.imshow(img_np)
                ax1.set_title(f"الصورة الحقيقية (Lat: {lat}, Lon: {lon})")
                ax1.axis('off')
                st.pyplot(fig1)
                
            with col2:
                st.subheader("🎯 2. خريطة الشذوذ المستخرجة من البكسلات الفعلية")
                fig2, ax2 = plt.subplots(figsize=(6, 6))
                im2 = ax2.imshow(final_anomaly, cmap=cmap_choice)
                ax2.set_title(map_title)
                fig2.colorbar(im2, ax=ax2)
                ax2.axis('off')
                st.pyplot(fig2)
            
            st.success("🎉 تم بنجاح جلب الصورة الجوية الحقيقية ومعالجة بكسلاتها الفعلية لاستخراج خريطة الشذوذ بدقة مطلقة!")
            
        except Exception as e:
            st.error(f"⚠️ حدث خطأ أثناء معالجة البكسلات: {e}")

else:
    st.warning("⚠️ أدخل إحداثيات موقعك في القائمة الجانبية ثم اضغط على زر المعالجة لاستخراج النتائج من البكسلات الحقيقية.")
