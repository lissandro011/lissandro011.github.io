"""Pruebas de conversión: no necesitan WhatsApp, solo Pillow y ffmpeg."""

import io
import json

import pytest
from conftest import make_video, needs_ffmpeg
from PIL import Image, ImageDraw

import sticker
from sticker import StickerError, StickerOptions, inspect_webp

OPTS = StickerOptions()
NO_MARK = StickerOptions(watermark="")


def jpeg(size, color=(200, 30, 30), noise=False, exif=None) -> bytes:
    img = Image.new("RGB", size, color)
    if noise:
        img = Image.blend(img, Image.effect_noise(size, 90).convert("RGB"), 0.6)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95, **({"exif": exif} if exif else {}))
    return buf.getvalue()


def rgba_at(webp: bytes, xy, frame=0):
    with Image.open(io.BytesIO(webp)) as img:
        img.seek(frame)
        return img.convert("RGBA").getpixel(xy)


def opaque_box(webp: bytes, frame=0):
    """Caja (izq, arriba, der, abajo) de los píxeles no transparentes."""
    with Image.open(io.BytesIO(webp)) as img:
        img.seek(frame)
        return img.convert("RGBA").getchannel("A").point(lambda a: 255 if a > 10 else 0).getbbox()


# --------------------------------------------------------------------------- #
# EXIF / contenedor WebP
# --------------------------------------------------------------------------- #


def test_exif_tiene_formato_de_whatsapp():
    exif = sticker.build_exif("Licha.bot", "Licha.bot")
    assert exif[:4] == b"II*\x00"
    assert int.from_bytes(exif[10:12], "little") == 0x5741  # tag de metadatos de sticker
    length = int.from_bytes(exif[14:18], "little")
    data = json.loads(exif[22 : 22 + length])
    assert data["sticker-pack-name"] == "Licha.bot"
    assert data["sticker-pack-publisher"] == "Licha.bot"


def test_add_exif_en_webp_animado_sin_recomprimir():
    frames = [Image.new("RGBA", (64, 64), c) for c in ((255, 0, 0, 255), (0, 0, 255, 128))]
    buf = io.BytesIO()
    frames[0].save(buf, "WEBP", save_all=True, append_images=frames[1:], duration=100, loop=0)
    exif = sticker.build_exif("Pack", "Autor")

    out = sticker.add_exif_to_webp(buf.getvalue(), exif)
    out2 = sticker.add_exif_to_webp(out, exif)  # reemplaza, no duplica

    assert [f for f, _ in sticker.iter_webp_chunks(out2)].count(b"EXIF") == 1
    with Image.open(io.BytesIO(out2)) as img:
        assert img.n_frames == 2
        assert img.info["exif"] == exif
    assert inspect_webp(out2)["exif"]["sticker-pack-publisher"] == "Autor"


def test_add_exif_rechaza_webp_simple():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "WEBP")
    with pytest.raises(ValueError):
        sticker.add_exif_to_webp(buf.getvalue(), b"x")


# --------------------------------------------------------------------------- #
# Imágenes
# --------------------------------------------------------------------------- #


def test_foto_grande_queda_512_y_bajo_100kb():
    out = sticker.image_to_sticker(jpeg((4000, 3000), noise=True), OPTS)
    info = inspect_webp(out)
    assert (info["width"], info["height"]) == (512, 512)
    assert info["bytes"] < 100 * 1024
    assert info["frames"] == 1 and not info["animated"]
    assert info["exif"]["sticker-pack-name"] == "Licha.bot"


def test_mantiene_proporcion_con_fondo_transparente():
    out = sticker.image_to_sticker(jpeg((800, 400)), NO_MARK)
    assert rgba_at(out, (5, 5))[3] == 0  # franja superior transparente
    assert rgba_at(out, (256, 256))[3] == 255
    assert opaque_box(out) == (0, 128, 512, 384)  # 2:1 -> 512x256 centrado


def test_imagen_chica_se_agranda():
    out = sticker.image_to_sticker(jpeg((40, 40)), NO_MARK)
    assert opaque_box(out) == (0, 0, 512, 512)


def test_respeta_rotacion_exif_de_la_camara():
    exif = Image.Exif()
    exif[0x0112] = 6  # "rotar 90°": la foto apaisada se ve vertical
    out = sticker.image_to_sticker(jpeg((800, 400), exif=exif.tobytes()), NO_MARK)
    left, top, right, bottom = opaque_box(out)
    assert bottom - top == 512 and right - left == 256


def test_png_transparente_conserva_transparencia():
    img = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse([50, 50, 250, 250], fill=(0, 200, 0, 255))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    out = sticker.image_to_sticker(buf.getvalue(), NO_MARK)
    assert rgba_at(out, (10, 10))[3] == 0
    assert rgba_at(out, (256, 256))[3] == 255


def test_marca_de_agua_abajo_a_la_derecha():
    data = jpeg((512, 512), color=(20, 60, 200))
    with_mark = sticker.image_to_sticker(data, OPTS)
    without = sticker.image_to_sticker(data, NO_MARK)

    def max_red(webp, box):
        with Image.open(io.BytesIO(webp)) as img:
            return img.convert("RGB").crop(box).getchannel("R").getextrema()[1]

    corner, top_left = (300, 440, 512, 512), (0, 0, 200, 60)
    # La marca (texto blanco) aparece en la esquina inferior derecha y no arriba a la izquierda.
    assert max_red(with_mark, corner) > 200
    assert max_red(without, corner) < 80
    assert max_red(with_mark, top_left) < 80


def test_imagen_invalida_da_error_corto():
    with pytest.raises(StickerError) as err:
        sticker.image_to_sticker(b"esto no es una imagen", OPTS)
    assert err.value.user_message == "No pude leer la imagen."


def test_respeta_el_limite_configurado():
    out = sticker.image_to_sticker(jpeg((2000, 2000), noise=True), StickerOptions(image_max_bytes=15 * 1024))
    assert len(out) <= 15 * 1024


# --------------------------------------------------------------------------- #
# Videos / GIF
# --------------------------------------------------------------------------- #


def total_duration_ms(webp: bytes) -> int:
    with Image.open(io.BytesIO(webp)) as img:
        total = 0
        for i in range(img.n_frames):
            img.seek(i)
            img.load()  # Pillow completa info["duration"] al cargar el cuadro
            total += img.info["duration"]
        return total


@needs_ffmpeg
def test_video_a_sticker_animado(tmp_path):
    data = make_video(tmp_path / "v.mp4", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30", "-t", "3",
                      "-pix_fmt", "yuv420p")  # fmt: skip
    out = sticker.video_to_sticker(data, OPTS)
    info = inspect_webp(out)
    assert (info["width"], info["height"]) == (512, 512)
    assert info["animated"] and info["frames"] >= 30
    assert info["bytes"] < 500 * 1024
    assert info["exif"]["sticker-pack-name"] == "Licha.bot"
    assert rgba_at(out, (5, 5))[3] == 0  # 16:9 -> franjas transparentes
    assert rgba_at(out, (256, 256))[3] == 255
    assert 2900 <= total_duration_ms(out) <= 3100


@needs_ffmpeg
def test_gif_a_sticker_animado(tmp_path):
    data = make_video(tmp_path / "a.gif", "-f", "lavfi", "-i", "testsrc=size=200x200:rate=10", "-t", "2")
    info = inspect_webp(sticker.video_to_sticker(data, OPTS))
    assert info["animated"] and (info["width"], info["height"]) == (512, 512)


@needs_ffmpeg
def test_video_ruidoso_entra_en_500kb(tmp_path):
    data = make_video(tmp_path / "ruido.mp4", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30",
                      "-vf", "noise=alls=40:allf=t", "-t", "5", "-pix_fmt", "yuv420p")  # fmt: skip
    assert len(sticker.video_to_sticker(data, OPTS)) < 500 * 1024


@needs_ffmpeg
def test_video_largo_se_rechaza(tmp_path):
    data = make_video(tmp_path / "largo.mp4", "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=15", "-t", "12",
                      "-pix_fmt", "yuv420p")  # fmt: skip
    with pytest.raises(StickerError) as err:
        sticker.video_to_sticker(data, OPTS)
    assert "máximo es 10 s" in err.value.user_message


@needs_ffmpeg
def test_video_de_10_4_s_se_recorta_a_10(tmp_path):
    data = make_video(tmp_path / "v.mp4", "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=15", "-t", "10.4",
                      "-pix_fmt", "yuv420p")  # fmt: skip
    assert total_duration_ms(sticker.video_to_sticker(data, OPTS)) <= 10_050


@needs_ffmpeg
def test_video_vertical_de_celular(tmp_path):
    horizontal = tmp_path / "h.mp4"
    make_video(horizontal, "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30", "-t", "2", "-pix_fmt", "yuv420p")
    data = make_video(tmp_path / "rot.mp4", "-display_rotation", "90", "-i", str(horizontal), "-c", "copy")
    out = sticker.video_to_sticker(data, NO_MARK)
    left, top, right, bottom = opaque_box(out, frame=5)
    assert bottom - top > right - left  # se ve vertical, como en el teléfono


@needs_ffmpeg
def test_video_de_un_cuadro_sale_estatico_y_transparente(tmp_path):
    data = make_video(tmp_path / "uno.mp4", "-f", "lavfi", "-i", "testsrc2=size=640x360", "-frames:v", "1",
                      "-pix_fmt", "yuv420p")  # fmt: skip
    out = sticker.video_to_sticker(data, OPTS)
    info = inspect_webp(out)
    assert info["frames"] == 1 and not info["animated"]
    assert info["bytes"] < 100 * 1024
    assert info["exif"]["sticker-pack-name"] == "Licha.bot"
    assert rgba_at(out, (5, 5))[3] == 0


@needs_ffmpeg
def test_archivo_sin_video_da_error(tmp_path):
    data = make_video(tmp_path / "a.m4a", "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2")
    with pytest.raises(StickerError) as err:
        sticker.video_to_sticker(data, OPTS)
    assert err.value.user_message == "El archivo no tiene video."


@needs_ffmpeg
def test_video_corrupto_da_error(tmp_path):
    with pytest.raises(StickerError):
        sticker.video_to_sticker(b"\x00" * 1000, OPTS)
