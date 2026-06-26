import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# إعداد الصفحة وتصميم الواجهة العربية
st.set_page_config(page_title="النظام الجيوفيزيائي", layout="wide")

st.markdown("""
<style>
    .main { text-align: right; direction: rtl; }
    h1, h2, h3 { color: #007bff; }
    body { background-color: #ffffff; }
    iframe { width: 100% !important; height: 500px !important; }
</style>
""", unsafe_allow_html=True)

st.title("🌍 نظام التحليل الهيدروجيولوجي - خرائط جوجل")
st.write("---")

# القائمة الجانبية للتحكم
st.sidebar.header("🛠️ أدوات التحكم")
task = st.sidebar.selectbox("اختر المهمة المطلوبة:", ["🛰️ صور جوجل الجوية والإحداثيات", "📊 المهام السابقة"])

if task == "🛰️ صور جوجل الجوية والإحداثيات":
    st.subheader("🛰️ مستكشف صور جوجل مابس الفضائية عالية الدقة")
    
    # مدخلات يدوية لكتابة الإحداثيات والتحكم بالخريطة من الأعلى
    st.write("🔍 **اكتب الإحداثيات هنا للانتقال والبحث المباشر:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        search_lat = st.number_input("خط العرض (Latitude):", value=16.270000, format="%.6f")
    with col2:
        search_lon = st.number_input("خط الطول (Longitude):", value=43.740000, format="%.6f")
    with col3:
        zoom_level = st.slider("مستوى التقريب (Zoom):", min_value=1, max_value=20, value=13)

    # خيار رفع ملف الإحداثيات من القائمة الجانبية
    uploaded_file = st.sidebar.file_uploader("ارفع ملف الإحداثيات (CSV/Excel)", type=["csv", "xlsx"])

    # رابط سيرفر خرائط جوجل الفضائية الرسمي (الأوضح والأعلى دقة)
    google_satellite_url = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
    
    # بناء الخريطة وتثبيتها على الإحداثيات المدخلة أعلاه
    m = folium.Map(
        location=[search_lat, search_lon], 
        zoom_start=zoom_level, 
        tiles=google_satellite_url, 
        attr='Google Satellite'
    )
    
    # إضافة خيار الهجين (أسماء المناطق فوق صور جوجل)
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google Hybrid',
        name='إظهار أسماء المناطق والشوارع',
        overlay=True,
        control=True
    ).add_to(m)
    
    # وضع علامة تثبيت حمراء عند الإحداثي المكتوب في الخانات أعلاه
    folium.Marker(
        location=[search_lat, search_lon],
        popup=f"الموقع الحالي المبحوث عنه:<br>{search_lat}, {search_lon}",
        icon=folium.Icon(color="red", icon="screenshot", prefix="glyphicon")
    ).add_to(m)
    
    folium.LayerControl().add_to(m)

    # معالجة ملف الإحداثيات المرفوع إن وجد وإسقاط النقاط تلقائياً
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
                
            lat_col = [col for col in df.columns if 'lat' in col.lower() or 'عرض' in col][0]
            lon_col = [col for col in df.columns if 'lon' in col.lower() or 'طول' in col][0]
            name_col = [col for col in df.columns if 'name' in col.lower() or 'اسم' in col or 'id' in col.lower()][0]
            
            for index, row in df.iterrows():
                folium.Marker(
                    location=[row[lat_col], row[lon_col]],
                    popup=f"📍 {row[name_col]}<br>Lat: {row[lat_col]}<br>Lon: {row[lon_col]}",
                    icon=folium.Icon(color="blue", icon="info-sign")
                ).add_to(m)
            st.success("✅ تم إسقاط نقاط الملف الحركي على خريطة جوجل!")
        except Exception as e:
            st.error("⚠️ تأكد من أسماء أعمدة الإحداثيات في الملف.")

    # عرض خريطة جوجل التفاعلية
    st.write("👇 **خريطة جوجل الفضائية التفاعلية (تنتقل تلقائياً للأرقام المكتوبة أعلاه):**")
    map_data = st_folium(m, width="100%", height=500, key="hydro_google_map_v3")
    
    # التقاط الإحداثيات عند النقر بالإصبع على صور جوجل
    if map_data and map_data.get("last_clicked"):
        clicked_lat = map_data["last_clicked"]["lat"]
        clicked_lng = map_data["last_clicked"]["lng"]
        st.info(f"📍 **الإحداثيات الناتجة عن نقرتك الحالية:** {clicked_lat} , {clicked_lng}")

elif task == "📊 المهام السابقة":
    st.subheader("📊 أدوات التحليل ومعالجة البيانات الحقلية")
    st.write("هنا يتم تفعيل كافة الحسابات السابقة للـ Numpy والمصفوفات.")
