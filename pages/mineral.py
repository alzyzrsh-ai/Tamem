import streamlit as st
import matplotlib.pyplot as plt
import urllib.request
import io
from PIL import Image

st.set_page_config(page_title="SanbGeo - Real Aerial Image", layout="centered")

st.title("🛰️ عرض الصورة الجوية الحقيقية (Google Earth Style)")
st.markdown("عرض مباشر لصورة الأقمار الصناعية الحقيقية لسطح الأرض بناءً على إحداثيات موقعك.")

# لوحة التحكم لإدخال الإحداثيات
st.sidebar.header("📍 إحداثيات الموقع")
lat = st.sidebar.number_input("خط العرض (Latitude)", value=15.3694, format="%.4f")
lon = st.sidebar.number_input("خط الطول (Longitude)", value=44.1910, format="%.4f")
zoom_level = st.sidebar.slider("مستوى التقريب (Zoom Level)", min_value=10, max_value=17, value=14)

if st.button("🌐 جلب وعرض الصورة الجوية الحقيقية"):
    with st.spinner("جاري جلب الصورة الجوية الحقيقية للموقع..."):
        try:
            # تحويل الإحداثيات إلى بلاطة خرائط (XYZ Tile) لجلب صورة حقيقية لسطح الأرض
            import math
            lat_rad = math.radians(lat)
            n = 2.0 ** zoom_level
            xtile = int((lon + 180.0) / 360.0 * n)
            ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
            
            # رابط جلب الصورة الجوية الحقيقية (ArcGIS World Imagery أو Esri مشابه لجوجل إيرث)
            tile_url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{zoom_level}/{ytile}/{xtile}"
            
            req = urllib.request.Request(
                tile_url, 
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req) as response:
                image_data = response.read()
                
            img = Image.open(io.BytesIO(image_data))
            
            # عرض الصورة الجوية الحقيقية بوضوح
            st.markdown("---")
            st.subheader(f"🌍 الصورة الجوية الحقيقية للموقع (خط العرض: {lat}, خط الطول: {lon})")
            
            fig, ax = plt.subplots(figsize=(8, 8))
            ax.imshow(img)
            ax.axis('off')
            st.pyplot(fig)
            
            st.success("✅ تم جلب وعرض الصورة الجوية الحقيقية بنجاح تام!")
            
        except Exception as e:
            st.error(f"⚠️ حدث خطأ أثناء جلب الصورة: {e}")

else:
    st.warning("⚠️ أدخل الإحداثيات في القائمة الجانبية ثم اضغط على زر جلب الصورة الجوية لعرضها فوراً.")
