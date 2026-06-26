import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# إعداد الصفحة وتصميم الواجهة العربية
st.set_page_config(page_title="النظام الجيوفيزيائي المتكامل", layout="wide")

st.markdown("""
<style>
    .main { text-align: right; direction: rtl; }
    h1, h2, h3 { color: #007bff; }
    body { background-color: #ffffff; }
</style>
""", unsafe_allow_html=True)

st.title("🌍 نظام الاستكشاف الهيدروجيولوجي الذكي ومعالجة البيانات")
st.write("---")

# القائمة الجانبية للتحكم بالمهام
st.sidebar.header("🛠️ أدوات التحكم")
task = st.sidebar.selectbox("اختر المهمة المطلوبة:", [
    "🛰️ الاستكشاف والربط مع AlpineQuest", 
    "📊 برنامجنا الرائع (معالجة واستقطاع البيانات الجيوفيزيائية)"
])

# نظام الذاكرة المؤقتة لنقل المنطقة المستقطعة بين الصفحات
if 'cropped_area' not in st.session_state:
    st.session_state['cropped_area'] = None

if task == "🛰️ الاستكشاف والربط مع AlpineQuest":
    st.subheader("🛰️ تحديد الإحداثيات والربط الميداني")
    
    col1, col2 = st.columns(2)
    with col1:
        search_lat = st.number_input("خط العرض المركزي (Latitude):", value=16.270000, format="%.6f")
    with col2:
        search_lon = st.number_input("خط الطول المركزي (Longitude):", value=43.740000, format="%.6f")
    
    alpine_link = f"geo:{search_lat},{search_lon}?q={search_lat},{search_lon}(الهدف)"
    st.markdown(f'<a href="{alpine_link}"><button style="width:100%; background-color:#d9534f; color:white; font-size:16px; font-weight:bold; padding:10px; border:none; border-radius:8px; cursor:pointer;">🗺️ فتح الموقع الميداني في AlpineQuest</button></a>', unsafe_allow_html=True)
    
    st.write("---")
    # ✂️ أداة استقطاع حدود المنطقة الحقلية (Bounding Box)
    st.subheader("✂️ أداة استقطاع منطقة الدراسة (Geographic Cropping)")
    st.write("حدد أبعاد المربع الحركي لاستقطاع المنطقة المحيطة بالبئر وإرسالها لبرنامج المعالجة:")
    
    crop_col1, crop_col2 = st.columns(2)
    with crop_col1:
        lat_buffer = st.slider("نطاق الاستقطاع الرأسي (Latitude Span Delta):", 0.001, 0.050, 0.010, format="%.3f")
    with crop_col2:
        lon_buffer = st.slider("نطاق الاستقطاع الأفقي (Longitude Span Delta):", 0.001, 0.050, 0.010, format="%.3f")
    
    # حساب أبعاد المربع المستقطع
    min_lat, max_lat = search_lat - lat_buffer, search_lat + lat_buffer
    min_lon, max_lon = search_lon - lon_buffer, search_lon + lon_buffer
    
    st.info(f"📐 حدود المنطقة المستقطعة حالياً:\n* خط العرض: من {min_lat:.4f} إلى {max_lat:.4f}\n* خط الطول: من {min_lon:.4f} إلى {max_lon:.4f}")
    
    if st.button("🚀 اعتماد استقطاع هذه المنطقة وإرسالها للمعالجة"):
        st.session_state['cropped_area'] = {
            'center': (search_lat, search_lon),
            'bounds': (min_lat, max_lat, min_lon, max_lon),
            'grid_size': 50 # شبكة مصفوفة المعالجة
        }
        st.success("🎯 تم حفظ واستقطاع المنطقة بنجاح! انتقل الآن إلى سهم (برنامجنا الرائع) من القائمة الجانبية لبدء المعالجة.")

elif task == "📊 برنامجنا الرائع (معالجة واستقطاع البيانات الجيوفيزيائية)":
    st.subheader("📊 لوحة المعالجة الرياضية والرسومية للمنطقة المستقطعة")
    
    if st.session_state['cropped_area'] is None:
        st.warning("⚠️ لم تقم باستقطاع أي منطقة بعد. يرجى الذهاب أولاً لقسم الاستكشاف وتحديد المنطقة المستهدفة.")
    else:
        area = st.session_state['cropped_area']
        st.success(f"✅ تم تحميل بيانات الاستقطاع الجغرافي للمركز: {area['center']}")
        
        # محاكاة توليد مصفوفة تضاريس أو مقاومية كهربائية (Resistivity/Elevation) للمنطقة المستقطعة باستخدام Numpy
        st.write("⚙️ **جاري تحويل الإحداثيات الجغرافية المستقطعة إلى مصفوفة رقمية ثنائية الأبعاد...**")
        
        min_lat, max_lat, min_lon, max_lon = area['bounds']
        x = np.linspace(min_lon, max_lon, area['grid_size'])
        y = np.linspace(min_lat, max_lat, area['grid_size'])
        X, Y = np.meshgrid(x, y)
        
        # معادلة رياضية جيوفيزيائية تحاكي تغير الشذوذ أو المقاومية تحت السطحية في المربع المستقطع
        Z = np.sin(X*100) * np.cos(Y*100) * 50 + 100 
        
        # رسم الخريطة الكنتورية والمجسمة للمنطقة المستقطعة بـ Matplotlib
        st.write("📈 **التحليل الكنتوري الرقمي ثنائي الأبعاد للمنطقة المستقطعة:**")
        fig, ax = plt.subplots(figsize=(8, 5))
        contour = ax.contourf(X, Y, Z, cmap='terrain', levels=20)
        fig.colorbar(contour, ax=ax, label="الارتفاع الرقمي / المقاومية النوعية (Ohm.m)")
        ax.set_title("Digital Terrain & Geological Analysis of Cropped Area")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        
        # وضع علامة البئر في المركز
        ax.plot(area['center'][1], area['center'][0], 'ro', label="📍 بئر الاستكشاف")
        ax.legend()
        
        st.pyplot(fig)
        
        # عرض البيانات كجدول رقمي جاهز للتصدير
        st.write("📂 **البيانات الرقمية المستقطعة والمستعدة للتحليل الهيدرولوجي:**")
        df_cropped = pd.DataFrame({
            'خط الطول (X)': X.flatten(),
            'خط العرض (Y)': Y.flatten(),
            'القيم المحسوبة (Z)': Z.flatten()
        })
        st.dataframe(df_cropped.head(100))
