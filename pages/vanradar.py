import cv2
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from scipy.ndimage import median_filter


def process_sar_gravel_channels(input_tif_path, output_tif_path=None):
    # 1. قراءة الملف الراداري واستخراج الإسقاط الجغرافي
    with rasterio.open(input_tif_path) as src:
        sar_band = src.read(1)
        profile = src.profile.copy()

    # 2. تنظيف الضوضاء الرادارية (Speckle Noise Filtering)
    # فلتر الميديان يحافظ على حواف القنوات ويتخلص من النقاط العشوائية
    denoised_band = median_filter(sar_band, size=3)

    # 3. تحسين التباين (Contrast Stretching / Percentile Clipping)
    valid_pixels = denoised_band[np.isfinite(denoised_band)]
    p2, p98 = np.percentile(valid_pixels, (2, 98))
    clipped_band = np.clip(denoised_band, p2, p98)

    # تحويل البيانات إلى نطاق 8-bit (0-255) لمعالجتها بواسطة OpenCV
    norm_band = cv2.normalize(
        clipped_band, None, 0, 255, cv2.NORM_MINMAX
    ).astype(np.uint8)

    # 4. عزل الانعكاسات العالية (High Backscatter Thresholding)
    # استخدام خوارزمية Otsu لتحديد الحد الفاصل تلقائياً بين الحصى الخشن والطين الأملس
    _, binary_gravel_mask = cv2.threshold(
        norm_band, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    # 5. تحسين شكل القنوات بالمورفولوجيا الرقمية (Morphological Operations)
    kernel_clean = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    kernel_connect = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))

    # إزالة التشويش النقطي الصغير
    cleaned_mask = cv2.morphologyEx(
        binary_gravel_mask, cv2.MORPH_OPEN, kernel_clean
    )
    # ربط الفجوات بين أجزاء القنوات الحصوية المقطعة
    final_channels_mask = cv2.morphologyEx(
        cleaned_mask, cv2.MORPH_CLOSE, kernel_connect
    )

    # 6. تصدير النتيجة كملف GeoTIFF جغرافي مُسند
    if output_tif_path:
        profile.update(dtype=rasterio.uint8, count=1, nodata=0)
        with rasterio.open(output_tif_path, "w", **profile) as dst:
            dst.write(final_channels_mask, 1)
        print(f"تم تصدير قنوات الحصى الجغرافية بنجاح إلى: {output_tif_path}")

    # 7. عرض النتائج
    plt.figure(figsize=(12, 6))

    plt.subplot(1, 2, 1)
    plt.imshow(norm_band, cmap="gray")
    plt.title("الصورة الرادارية الأصلية (SAR Intensity)")
    plt.axis("off")

    plt.subplot(1, 2, 2)
    plt.imshow(final_channels_mask, cmap="cyan")
    plt.title("نطاقات الحصى وقنوات الأودية المستخرجة")
    plt.axis("off")

    plt.tight_layout()
    plt.show()

    return final_channels_mask


# تشغيل الكود على الملف الخاص بك
# process_sar_gravel_channels('Alؤاداريه القدميProject_Map (6).tif', 'Gravel_Channels_Output.tif')
