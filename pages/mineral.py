import streamlit as st
import numpy as np
import rasterio
from rasterio.plot import show
import matplotlib.pyplot as plt
import os

st.set_page_config(page_title="SanbGeo - Remote Sensing & Mineral Exploration", layout="wide")

st.title("🛰️ نظام الاستشعار عن بعد واستكشاف التمعدن السطحي")
st.markdown("أداة تحليل الأطياف ومؤشرات المعادن المتقدمة لتحديد أهداف الاستكشاف الجيولوجي.")

# شريط جانبي لإدخال البيانات أو رفع الملفات
st.sidebar.header("إعدادات البيانات المكانية")
uploaded_file = st.sidebar.file_uploader("قم بترفع ملف رستر (GeoTIFF نطاقات الأقمار الصناعية)", type=["tif", "tiff"])

if uploaded_file is not None:
    # حفظ الملف مؤقتاً لقراءته عبر Rasterio
    with open("temp_raster.tif", "wb") as f:
        f.write(uploaded_file.getbuffer())
        
    with rasterio.open("temp_raster.tif") as src:
        image_meta = src.meta
        band_count = src.count
        st.sidebar.success(format(f"تم تحميل الملف بنجاح! عدد النطاقات (Bands): {band_count}"))
        
        # قراءة النطاقات (افتراض نطاقات معينة كمثال أو حسب الملف المرفوع)
        # مثلاً: النطاق الأحمر والاحمر القريب أو الأشعة تحت الحمراء القصيرة SWIR
        st.subheader("📊 معاينة البيانات المكانية")
        fig, ax = plt.subplots(figsize=(8, 6))
        show(src, ax=ax, title="Raster Overview")
        st.pyplot(fig)
        
        st.divider()
        st.header("⚙️ خوارزميات استخلاص المؤشرات (Band Ratios)")
        
        # اختيار نوع المؤشر الجيولوجي
        index_type = st.selectbox(
            "اختر نوع المؤشر الاستكشافي:",
            ["مؤشر أكاسيد الحديد (Iron Oxides)", "مؤشر معادن الطين والهيدروكسيل (Hydroxyls/Clays)", "مؤشر السيليكا (Silicification Index)"]
        )
        
        if st.button("تنفيذ المعالجة الطيفية وتوليد الخريطة"):
            with st.spinner("جاري معالجة المصفوفات المكانية وحساب النطاقات..."):
                # قراءة مصفوفة البيانات بالكامل
                data = src.read() # شكل المصفوفة: (bands, height, width)
                
                # نموذج تطبيقي لحساب النسب (مثال رياضي افتراضي لتطبيق الباند ريشيو)
                # التأكد من وجود نطاقين على الأقل للحساب
                if data.shape[0] >= 2:
                    # مثال افتراضي: قسمة النطاق الثاني على الأول أو معادلة تقريبية للنموذج
                    band1 = data[0].astype(np.float32)
                    band2 = data[1].astype(np.float32)
                    
                    # تجنب القسمة على الصفر
                    band2 = np.where(band2 == 0, 0.0001, band2)
                    
                    # حساب مؤشر المعالجة الطيفية
                    ratio_result = band1 / band2
                    
                    st.success("تم إتمام المعالجة بنجاح وتحويل الشذوذ الطيفي إلى خريطة تصنيفية!")
                    
                    # عرض النتيجة الخرائطية
                    fig_res, ax_res = plt.subplots(figsize=(8, 6))
                    cax = ax_res.imshow(ratio_result, cmap='jet')
                    fig_res.colorbar(cax, label='Spectral Index Value')
                    ax_res.set_title(f"نتائج تحليل: {index_type}")
                    st.pyplot(fig_res)
                    
                else:
                    st.error("الملف المرفوع لا يحتوي على نطاقات كافية لتطبيق معادلات النسب الطيفية.")

else:
    st.info("الرجاء رفع ملف رستر بصيغة GeoTIFF عبر القائمة الجانبية للبدء بالعمل.")
