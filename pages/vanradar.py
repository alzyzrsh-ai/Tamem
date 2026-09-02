import cv2
import numpy as np
import rasterio
from scipy.ndimage import median_filter
import streamlit as st

st.title("تحليل قنوات الحصى من صور SAR")

uploaded_file = st.file_uploader(
    "قم برفع ملف GeoTIFF الخاص بالرادار", type=["tif", "tiff"]
)

if uploaded_file is not None:
    try:
        with rasterio.open(uploaded_file) as src:
            sar_band = src.read(1)

        denoised_band = median_filter(sar_band, size=3)

        valid_pixels = denoised_band[np.isfinite(denoised_band)]
        if len(valid_pixels) > 0:
            p2, p98 = np.percentile(valid_pixels, (2, 98))
            clipped_band = np.clip(denoised_band, p2, p98)

            norm_band = cv2.normalize(
                clipped_band, None, 0, 255, cv2.NORM_MINMAX
            ).astype(np.uint8)

            _, binary_gravel_mask = cv2.threshold(
                norm_band, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )

            kernel_clean = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            kernel_connect = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))

            cleaned_mask = cv2.morphologyEx(
                binary_gravel_mask, cv2.MORPH_OPEN, kernel_clean
            )
            final_mask = cv2.morphologyEx(
                cleaned_mask, cv2.MORPH_CLOSE, kernel_connect
            )

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("الصورة الرادارية الأصلية")
                st.image(norm_band, use_container_width=True)

            with col2:
                st.subheader("قنوات الحصى المستخرجة")
                st.image(final_mask, use_container_width=True)

    except Exception as e:
        st.error(f"حدث خطأ أثناء معالجة الملف: {e}")
else:
    st.info("يرجى رفع ملف TIFF للبدء في المعالجة.")
