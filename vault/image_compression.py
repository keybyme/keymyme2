import io

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageOps

# Reduce el tamaño (KB) de una foto recién subida re-codificándola a menor
# calidad/resolución. 'alta' se maneja aparte (no se recomprime).
QUALITY_PRESETS = {
    "media": {"max_dimension": 1920, "jpeg_quality": 70, "webp_quality": 70, "png_compress_level": 8},
    "baja": {"max_dimension": 1280, "jpeg_quality": 45, "webp_quality": 45, "png_compress_level": 9},
}

# Formatos que sabemos re-codificar de forma segura. GIF (animación) y HEIC
# (Pillow no lo lee sin un plugin aparte) se dejan tal cual sin importar la
# calidad elegida.
COMPRESSIBLE_FORMATS = {"JPEG", "PNG", "WEBP"}


def compress_image(uploaded_file, quality):
    """Intenta re-codificar `uploaded_file` (un UploadedFile recién subido) a
    la calidad pedida. Devuelve un nuevo archivo más chico, o None si no aplica
    (calidad 'alta', formato no soportado, o la recompresión no redujo el
    tamaño) — en ese caso el llamador debe conservar el archivo original."""
    preset = QUALITY_PRESETS.get(quality)
    if preset is None:
        return None

    uploaded_file.seek(0)
    try:
        image = Image.open(uploaded_file)
        image.load()
    except Exception:
        return None
    finally:
        uploaded_file.seek(0)

    original_format = image.format
    if original_format not in COMPRESSIBLE_FORMATS:
        return None

    image = ImageOps.exif_transpose(image)

    max_dim = preset["max_dimension"]
    if max(image.size) > max_dim:
        image.thumbnail((max_dim, max_dim), Image.LANCZOS)

    save_kwargs = {"optimize": True}
    if original_format == "JPEG":
        if image.mode != "RGB":
            image = image.convert("RGB")
        save_kwargs["quality"] = preset["jpeg_quality"]
    elif original_format == "WEBP":
        save_kwargs["quality"] = preset["webp_quality"]
    else:  # PNG
        save_kwargs["compress_level"] = preset["png_compress_level"]

    buffer = io.BytesIO()
    image.save(buffer, format=original_format, **save_kwargs)
    compressed_size = buffer.tell()

    if compressed_size >= uploaded_file.size:
        return None

    return SimpleUploadedFile(
        name=uploaded_file.name,
        content=buffer.getvalue(),
        content_type=uploaded_file.content_type,
    )
