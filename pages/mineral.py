import streamlit as st
import matplotlib.pyplot as plt
import urllib.request
import io
from PIL import Image
import numpy as np
import math

st.set_page_config(page_title="SanbGeo - Blended Spectral Engine", layout="wide")

st.title("🛰️ المنظومة الجيولوجية: الدمج البصري والشفافية للشذوذ")
st.markdown("دمج خريطة الشذوذ الطيفي المستخرجة من البكسلات الفعلية فوق الصورة الجوية الحقيقية مع تحكم كامل بالشفافية لضمان دقة المطابقة.")

st.sidebar.header("📍 إحداثيات الموقع")
lat = st.sidebar.number_input("خط العرض (Latitude)", value=15.3694, format="%.4f")
lon = st.sidebar.number_input("خط الطول (Longitude)", value=44.1910, format="%.4f")
zoom_level = st.sidebar.slider("مستوى التقريب (Zoom Level)", min_value=10, max_value=17, value=14)

st.sidebar.divider()
st.sidebar.header("⚙️ إعدادات الدمج والشفافية")
alpha_val = st.sidebar.slider("شفافية خريطة الشذوذ (Opacity Alpha)", min_value=0.0, max_value=1.0, value=0.5, step=0.05)

index_type = st.sidebar.selectbox(
    "اختر مؤشر المعالجة البكسلية:",
    [
        "مؤشر أكاسيد الحديد المرئي (Red / Green)",
        "مؤشر الشذوذ والتباين السطحي (Brightness Index)",
        "مؤشر التشبع الطيفي للصخور (Saturation Contrast)"
    ]
)

if st.button("🌐 تنفيذ الدمج البصري واستخراج الشذوذ بدقة"):
    with st.spinner("جاري جلب الصورة الجوية ومعالجة البكسلات وتطبيق الدمج الشفاف..."):
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
            
            # 3. تطبيق معادلات حقيقية مستمدة من البكسلات الفعلية
            if "أكاسيد الحديد" in index_type:
                anomaly_matrix = R / G
                map_title = "دمج أكاسيد الحديد فوق الصورة الجوية (R / G)"
                cmap_choice = 'hot'
            elif "التباين السطحي" in index_type:
                anomaly_matrix = np.sqrt((R**2 + G**2 + B**2) / 3.0)
                map_title = "دمج التباين والسطوع السطحي"
                cmap_choice = 'plasma'
            else:
                max_val = np.maximum(np.maximum(R, G), B)
                min_val = np.minimum(np.minimum(R, G), B)
                anomaly_matrix = (max_val - min_val) / (max_val + 0.001)
                map_title = "دمج التشبع الطيفي الصخري"
                cmap_choice = 'inferno'

            p_min, p_max = np.percentile(anomaly_matrix, (2, 98))
            final_anomaly = np.clip((anomaly_matrix - p_min) / (p_max - p_min + 1e-5), 0, 1)

            # 4. العرض المرئي المدمج (صورة مرجعية مستقلة + نافذة الدمج الشفاف الاحترافية)
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🌍 1. الصورة الجوية الأصلية")
                fig1, ax1 = plt.subplots(figsize=(6, 6))
                ax1.imshow(img_np)
                ax1.set_title(f"الصورة الحقيقية (Lat: {lat}, Lon: {lon})")
                ax1.axis('off')
                st.pyplot(fig1)
                
            with col2:
                st.subheader("🎯 2. الدمج الاحترافي (الصورة + الشذوذ بشفافية)")
                fig2, ax2 = plt.subplots(figsize=(6, 6))
                # عرض الصورة الجوية كخلفية أساسية
                ax2.imshow(img_np)
                # إسقاط خريطة الشذوذ فوقها بدرجة شفافة (alpha) للتحكم الدقيق
                im2 = ax2.imshow(final_anomaly, cmap=cmap_choice, alpha=alpha_val)
                ax2.set_title(map_title)
                fig2.colorbar(im2, ax=ax2)
                ax2.axis('off')
                st.pyplot(fig2)
            
            st.success("🎉 تمت عملية دمج خريطة الشذوذ فوق الصورة الجوية الحقيقية مع التحكم بالشفافية بنجاح تام ودقة هندسية عالية!")
            
        except Exception as e:
            st.error(f"⚠️ حدث خطأ أثناء الدمج البصري: {e}")

else:
    st.warning("⚠️ حدد إحداثيات موقعك ومستوى الشفافية في القائمة الجانبية ثم اضغط على زر الدمج البصري.")
