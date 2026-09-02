import cv2
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from scipy.ndimage import median_filter
from skimage.morphology import skeletonize
import streamlit as st

st.title("تحليل ورسم قنوات الحصى من صور SAR")

uploaded_file = st.file_uploader(
    "قم برفع ملف GeoTIFF الخاص بالرادار", type=["tif", "tiff"]
)

if uploaded_file is not None:
    try:
        with rasterio.open(uploaded_file) as src:
            sar_band = src.read(1)
            # حساب مقياس الرسم (متر لكل بكسل) من التحويل الجغرافي
            pixel_size_x = abs(src.transform[0])

        # 1. فلترة الضوضاء وتنظيف الصورة
        denoised_band = median_filter(sar_band, size=3)
        valid_pixels = denoised_band[np.isfinite(denoised_band)]

        if len(valid_pixels) > 0:
            p2, p98 = np.percentile(valid_pixels, (2, 98))
            clipped_band = np.clip(denoised_band, p2, p98)
            norm_band = cv2.normalize(
                clipped_band, None, 0, 255, cv2.NORM_MINMAX
            ).astype(np.uint8)

            # 2. تحويل الصورة إلى تلوين حراري (Viridis Colormap)
            colored_sar = cv2.applyColorMap(norm_band, cv2.COLORMAP_VIRIDIS)
            colored_sar_rgb = cv2.cvtColor(colored_sar, cv2.COLOR_BGR2RGB)

            # 3. عزل الانعكاسات العالية (الحصى)
            _, binary_gravel_mask = cv2.threshold(
                norm_band, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )

            # 4. أداة استخراج ورسم سنترلاين القنوات (Skeletonization)
            binary_bool = binary_gravel_mask > 0
            skeleton = skeletonize(binary_bool)

            # دمج القنوات الملونة مع الصورة الأصلية (قنوات سيان على الخلفية)
            overlay = colored_sar_rgb.copy()
            overlay[skeleton] = [0, 255, 255]  # لون سيان ساطع للقنوات

            # 5. رسم النتائج مع إضافة مقياس الرسم (Scalebar) عبر Matplotlib
            fig, ax = plt.subplots(1, 2, figsize=(12, 6))

            # العرض الملون للأصل
            ax[0].imshow(colored_sar_rgb)
            ax[0].set_title("الصورة الرادارية الملونة (Viridis)")
            ax[0].axis("off")

            # عرض القنوات المستخرجة مع مقياس الرسم
            ax[1].imshow(overlay)
            ax[1].set_title("تتبع شبكة قنوات الحصى (Skeletonized Channels)")
            ax[1].axis("off")

            # إضافة مقياس الرسم أسفل الخريطة الثانية
            height, width = norm_band.shape
            scale_len_pixels = int(
                width * 0.2
            )  # طول المقياس يعادل 20% من عرض الصورة
            scale_len_km = (scale_len_pixels * pixel_size_x) / 1000.0

            if scale_len_km > 0:
                ax[1].plot(
                    [width * 0.05, width * 0.05 + scale_len_pixels],
                    [height * 0.92, height * 0.92],
                    color="white",
                    linewidth=4,
                )
                ax[1].text(
                    width * 0.05,
                    height * 0.89,
                    f"{scale_len_km:.1f} km",
                    color="white",
                    fontsize=12,
                    weight="bold",
                )

            st.pyplot(fig)

    except Exception as e:
        st.error(f"حدث خطأ أثناء معالجة الملف: {e}")
