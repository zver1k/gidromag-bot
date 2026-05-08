import hashlib
import logging
import os

logger = logging.getLogger(__name__)

_COMPRESS_THRESHOLD = 5 * 1024 * 1024  # 5 MB
_JPEG_QUALITY = 85


def compute_md5(file_path: str) -> str:
    h = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def convert_to_jpg(input_path: str, output_path: str) -> bool:
    """Convert image to JPEG. Returns True on success."""
    try:
        from PIL import Image
        with Image.open(input_path) as img:
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')
            img.save(output_path, 'JPEG', quality=95, optimize=True)
        logger.info(f"🔄 JFIF конвертирован в JPEG: {os.path.basename(input_path)}")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Не удалось конвертировать в JPEG: {e}")
        return False


def compress_photo(input_path: str, output_path: str) -> bool:
    """Compress photo if > 5MB. Returns True if file was compressed."""
    try:
        if os.path.getsize(input_path) <= _COMPRESS_THRESHOLD:
            return False
        from PIL import Image
        with Image.open(input_path) as img:
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')
            img.save(output_path, 'JPEG', quality=_JPEG_QUALITY, optimize=True)
        logger.info(f"🗜️ Фото сжато: {os.path.getsize(input_path)} → {os.path.getsize(output_path)} байт")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Не удалось сжать фото: {e}")
        return False
