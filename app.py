import streamlit as st
import pandas as pd
import pydeck as pdk

# إعداد الصفحة وتصميم الواجهة العربية المخصصة
st.set_page_config(page_title="النظام الجيوفيزيائي ثلاثي الأبعاد", layout="wide")

st.markdown("""
<style>
    .main { text-align: right; direction: rtl; }
    h1, h2, h3 { color: #007bff; }
    body { background-color: #ffffff; }
</style>
""", unsafe_allow_html=True)

st.title("🌍 نظام الاستكشاف الهيدروجيولوجي ثلاثي الأبعاد (3D)")
st.write("---")

# القائمة الجانبية للتحكم
st.sidebar.header("🛠️ أدوات التحكم")
task = st.sidebar.selectbox("اختر المهمة المطلوبة:", ["🛰️ المستكشف الفضائي ثلاثي الأبعاد 3D", "📊 المهام السابقة"])

if task == "🛰️ المستكشف الفضائي ثلاثي الأبعاد 3D":
    st.subheader("🛰️ عرض التضاريس والصور الجوية بزاوية ثلاثية الأبعاد")
    
    # خانات إدخال الإحداثيات والتحكم في زوايا الرؤية المجسمة
    st.write("🔍 **البحث والانتقال الفوري بالإحداثيات:**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        search_lat = st.number_input("خط العرض (Latitude):", value=16.270000, format="%.6f")
    with col2:
        search_lon = st.number_input("خط الطول (Longitude):", value=43.740000, format="%.6f")
    with col3:
        zoom_level = st.slider("مستوى التقريب (Zoom):", min_value=1, max_value=20, value=14)
    with col4:
        pitch_angle = st.slider("زاوية الإمالة المجسمة (Pitch 3D):", min_value=0, max_value=60, value=45)

    # خيار رفع ملف الإحداثيات من القائمة الجانبية
    uploaded_file = st.sidebar.file_uploader("ارفع ملف الإحداثيات (CSV/Excel)", type=["csv", "xlsx"])

    # تجهيز النقطة الأساسية للبحث كعلامة ثلاثية الأبعاد
    df_points = pd.DataFrame({
        'Lat': [search_lat],
        'Lon': [search_lon],
        'name': ['📍 الموقع المستهدف']
    })

    # دمج ملف المستخدم إن وجد
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_user = pd.read_csv(uploaded_file)
            else:
                df_user = pd.read_excel(uploaded_file)
                
            lat_col = [col for col in df_user.columns if 'lat' in col.lower() or 'عرض' in col][0]
            lon_col = [col for col in df_user.columns if 'lon' in col.lower() or 'طول' in col][0]
            
            df_user = df_user.rename(columns={lat_col: 'Lat', lon_col: 'Lon'})
            if 'name' not in df_user.columns:
                df_user['name'] = 'بئر مستهدف'
                
            df_points = pd.concat([df_points, df_user[['Lat', 'Lon', 'name']]], ignore_index=True)
            st.success("✅ تم إسقاط نقاط الملف حركياً!")
        except Exception as e:
            st.error("⚠️ تأكد من أسماء الأعمدة في ملفك.")

    # 🗺️ بناء واجهة العرض المجسم وثلاثي الأبعاد باستخدام Pydeck
    # نستخدم خريطة القمر الصناعي الرسمية (mapbox://styles/mapbox/satellite-v9) لدقة فائقة وثلاثية أبعاد
    view_state = pdk.ViewState(
        latitude=search_lat,
        longitude=search_lon,
        zoom=zoom_level,
        pitch=pitch_angle, # التحكم في زاوية النظر المائلة لرؤية التضاريس ثلاثية الأبعاد
        bearing=0
    )

    # طبقة لإظهار مواقع الآبار أو الأهداف كأعمدة حمراء ثلاثية الأبعاد
    layer = pdk.Layer(
        "ScatterplotLayer",
        df_points,
        get_position=["Lon", "Lat"],
        get_color=[255, 0, 0, 200],
        get_radius=100,
        pickable=True
    )

    # رندرة خريطة القمر الصناعي المجسمة
    r = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style="mapbox://styles/mapbox/satellite-v9", # قمر صناعي فائق الدقة ويدعم الإمالة
        tooltip={"text": "{name}\nLat: {Lat}\nLon: {Lon}"}
    )

    st.write("👇 **المستكشف الفضائي المجسم (تتحرك تلقائياً وتتحول للـ 3D عند تغيير الزاوية):**")
    st.pydeck_chart(r)

elif task == "📊 المهام السابقة":
    st.subheader("📊 أدوات التحليل ومعالجة البيانات الحقلية")
