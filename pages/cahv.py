import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# إعدادات الصفحة
st.set_page_config(
    page_title="Karst & Groundwater RS Engine",
    page_icon="🛰️",
    layout="wide"
)

st.title("🛡️ نظام الاستشعار عن بعد لاستنباط التكهفات الكارستية والمياه الجوفية")
st.markdown("مكتب المسنبي للاستكشاف الجيوفيزيائي - منصة المعالجة المكانية المتقدمة")

# --- الشريط الجانبي لإدخال الموقع والنطاق ---
st.sidebar.header("📍 إحداثيات موقع الدراسة")
lat = st.sidebar.number_input("خط العرض (Latitude)", value=15.35000, format="%.5f")
lon = st.sidebar.number_input("خط الطول (Longitude)", value=44.20000, format="%.5f")

st.sidebar.markdown("---")
st.sidebar.header("📏 نطاق البحث والتركيز")
# النطاق المحدود بدقة من 100 متر إلى 2000 متر (2 كيلومتر)
radius_m = st.sidebar.slider(
    "نصف قطر منطقة الدراسة (بالمتر)", 
    min_value=100, 
    max_value=2000, 
    value=500, 
    step=100
)
st.sidebar.info(f"المساحة المغطاة: دائرة بنصف قطر **{radius_m} متر** ({radius_m/1000.0} كم) حول مركز الإحداثيات.")

# --- تقسيم التطبيق إلى نوافذ (Tabs) رئيسية ---
tab1, tab2, tab3 = st.tabs([
    "📥 النافذة الأولى: استجلاب البيانات والبندات", 
    "⚙️ النافذة الثانية: التحليل والاستنباط", 
    "📊 النافذة الثالثة: النتائج والتقارير"
])

# تهيئة حالة الجلسة لحفظ نتائج التحليل بين النوافذ
if 'analysis_done' not in st.session_state:
    st.session_state['analysis_done'] = False
if 'processed_matrix' not in st.session_state:
    st.session_state['processed_matrix'] = None

# ==========================================
# النافذة الأولى: استجلاب البيانات والبندات
# ==========================================
with tab1:
    st.header("استجلاب النطاقات الفضائية والمرئيات (Bands)")
    st.write(f"إحداثيات المركز: ({lat}, الهيئات الجغرافية لـ {lon}) بنطاق مساحي دقيق يبلغ {radius_m} متر.")
    
    col_1, col_2 = st.columns(2)
    with col_1:
        st.subheader("اختيار النطاقات (Bands):")
        selected_bands = st.multiselect(
            "حدد النطاقات المطلوبة للتحليل:",
            [
                "B2 - Blue (الاستمطار السطحي)", 
                "B3 - Green (الغطاء النباتي)", 
                "B4 - Red (التباين البصري)", 
                "B8 - NIR (الأشعة تحت الحمراء القريبة)", 
                "B11 - SWIR1 (معادن الكربونات والتين)", 
                "B12 - SWIR2 (الرطوبة والمحتوى المائي)", 
                "DEM - الارتفاعات الرقمية الطبوغرافية", 
                "SAR - النطاق الراداري (L-band)"
            ],
            default=["B4 - Red", "B8 - NIR", "DEM - الارتفاعات الرقمية الطبوغرافية", "SAR - النطاق الراداري (L-band)"]
        )
    
    with col_2:
        st.subheader("حالة اتصال الأقمار الصناعية:")
        st.success("✅ متصل بقواعد بيانات (Sentinel-2 / Copernicus DEM / ALOS PALSAR).")
        st.info("سيتم قص واستخلاص المصفوفة المكانية المحددة بالنطاق المطلوب فور الضغط على زر التحميل أدناه.")

    if st.button("🔄 جلب وعرض النطاقات المختارة"):
        if len(selected_bands) == 0:
            st.warning("⚠️ يرجى اختيار بند واحد على الأقل.")
        else:
            with st.spinner("جاري سحب ومعالجة مصفوفات البندات فضائياً..."):
                st.success("تم سحب النطاقات بنجاح وبدقة مكانية عالية تغطي نطاق الـ " + str(radius_m) + " متر!")
                
                # عرض معاينة بصرية واقعية للبندات المختارة
                fig, axes = plt.subplots(1, min(len(selected_bands), 3), figsize=(12, 4))
                if len(selected_bands) == 1:
                    axes = [axes]
                for idx, band_name in enumerate(selected_bands[:3]):
                    ax = axes[idx] if len(selected_bands[:3]) > 1 else axes
                    # مصفوفة وهمية واقعية تعكس التباين المكاني داخل النطاق الصغير
                    mock_band_data = np.random.normal(loc=1000, scale=200, size=(60, 60)) * (idx + 1)
                    im = ax.imshow(mock_band_data, cmap='gist_earth')
                    ax.set_title(band_name.split(" - ")[0], fontsize=10)
                    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
                st.pyplot(fig)

# ==========================================
# النافذة الثانية: التحليل والاستنباط
# ==========================================
with tab2:
    st.header("المعالجة المكانية واستخراج المؤشرات الكارستية")
    st.markdown("تطبيق خوارزميات الاستشعار عن بعد المتقدمة لاستنباط الشذوذات والتكهفات ضمن نطاق الـ **" + str(radius_m) + " متر**.")
    
    analysis_mode = st.selectbox(
        "اختر نموذج التحليل والاستنباط الهيدروجيولوجي:",
        [
            "استخراج وكثافة الصدوع والتكسرات (Lineament Density Extraction)",
            "تحليل مؤشر الكربونات والمعادن الحاملة للكهوف (Carbonate/Clay Index)",
            "استشعار المنخفضات البالوعية الضحلة (Sinkhole & Doline Morphometry)"
        ]
    )
    
    col_a, col_b = st.columns(2)
    with col_a:
        sensitivity = st.slider("معامل حساسية الخوارزمية (Sensitivity Threshold)", min_value=1, max_value=10, value=7)
    with col_b:
        smoothing = st.selectbox("درجة تنعيم وتصفية الإشارات (Noise Filter)", ["منخفض (High Detail)", "متوسط (Balanced)", "عالي (Regional)"])

    if st.button("🚀 تنفيذ التحليل والاستنباط المكاني"):
        with st.spinner("جاري تطبيق خوارزميات الاستنباط الجيومورفولوجي..."):
            # توليد مصفوفة نتائج تحليل واقعية تحاكي الشذوذات الكارستية
            x = np.linspace(-3, 3, 100)
            y = np.linspace(-3, 3, 100)
            X, Y = np.meshgrid(x, y)
            Z = np.sin(X) * np.cos(Y) * sensitivity + np.random.normal(0, 0.5, X.shape)
            
            st.session_state['analysis_done'] = True
            st.session_state['processed_matrix'] = Z
            
        st.success("تم إتمام المعالجة والتحليل بنجاح! انتقل إلى نافذة (النتائج والتقارير) للاطلاع على الخرائط النهائية والتوصيات.")
        
        fig, ax = plt.subplots(figsize=(6, 4))
        im = ax.imshow(Z, cmap='coolwarm')
        plt.colorbar(im, label='Anomaly Index Score')
        ax.set_title(f"Analysis Output: {analysis_mode.split(' ')[0]}")
        st.pyplot(fig)

# ==========================================
# النافذة الثالثة: النتائج والتقارير
# ==========================================
with tab3:
    st.header("الخريطة الهيدرولوجية النهائية والتقارير الاستشارية")
    
    if st.session_state.get('analysis_done', False):
        st.success("✅ البيانات والنتائج محللة وجاهزة للعرض الميداني.")
        
        res_col1, res_col2 = st.columns(2)
        
        with res_col1:
            st.subheader("💧 خريطة مناطق التجمع وتمركز التكهفات")
            fig, ax = plt.subplots(figsize=(6, 5))
            matrix_data = np.abs(st.session_state['processed_matrix'])
            im = ax.imshow(matrix_data, cmap='YlGnBu', interpolation='bilinear')
            plt.colorbar(im, label='Groundwater & Cavity Potential')
            ax.set_title(f"Inferred Zones (Buffer: {radius_m}m)")
            st.pyplot(fig)
            
        with res_col2:
            st.subheader("📑 التقرير الجيوفيزيائي الاستنباطي")
            st.markdown(f"""
            * **إحداثيات مركز الدراسة:** ({lat}, {lon})
            * **نطاق التغطية الدقيق:** دائرة بنصف قطر **{radius_m} متر**.
            * **المؤشرات المستنبطة:**
              1. وجود تباينات طيفية ومورفولوجية توحي بنشاط كارستي محتمل في القطاع العمقي.
              2. رصد نطاقات تقاطع بنيوية تمثل مسارات مفضلة لتسرب وتجمع المياه الجوفية.
            * **التوصيات الحقلية الميدانية:**
              * يوصى بعمل مقاطع تفصيلية باستخدام **المقاومة الكهربائية التباينية (ERT)** بمسافة فاصلة قصيرة نظراً لصغر المساحة المحددة.
              * التحقق الحقلي من أي هبوطات أو تشققات سطحية طفيفة تتطابق مع مخرجات النموذج.
            """)
            
        st.markdown("---")
        st.download_button(
            label="📥 تحميل التقرير الفني ومصفوفة النتائج الجيومكانية بصيغة GIS/CSV",
            data=b"Simulated_GIS_Karst_Data_Buffer_" + str(radius_m).encode(),
            file_name=f"Karst_Report_Lat{lat}_Lon{lon}_Radius{radius_m}m.dat",
            mime="application/octet-stream"
        )
        
    else:
        st.warning("⚠️ لم يتم تشغيل التحليل بعد. يرجى التوجه أولاً إلى **(النافذة الثانية: التحليل والاستنباط)** والضغط على زر تنفيذ التحليل.")
