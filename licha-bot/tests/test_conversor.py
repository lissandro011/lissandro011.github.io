import io
import shutil
import subprocess

import pytest
from conftest import foto, gif, ruido, video
from PIL import Image

from licha_bot.conversor import (
    LIENZO,
    ErrorSticker,
    OpcionesSticker,
    construir_exif,
    crear_sticker,
    inspeccionar_webp,
    remuestrear,
    sticker_a_imagen,
)

OPC = OpcionesSticker(paquete="Mi pack", autor="Licha")


def alfa_en(datos: bytes, xy: tuple[int, int]) -> int:
    with Image.open(io.BytesIO(datos)) as img:
        return img.convert("RGBA").getpixel(xy)[3]


def test_foto_a_sticker_estatico():
    s = crear_sticker(foto(1200, 600), OPC)
    info = inspeccionar_webp(s.datos)
    assert not s.animado
    assert (info["ancho"], info["alto"]) == (LIENZO, LIENZO)
    assert info["bytes"] <= 100 * 1024
    assert info["exif"]["sticker-pack-name"] == "Mi pack"
    assert info["exif"]["sticker-pack-publisher"] == "Licha"


def test_mantiene_la_proporcion_con_bordes_transparentes():
    datos = crear_sticker(foto(1200, 600), OPC).datos  # foto apaisada: arriba y abajo quedan vacíos
    assert alfa_en(datos, (256, 5)) == 0
    assert alfa_en(datos, (256, 256)) == 255


def test_recortar_llena_el_cuadrado():
    datos = crear_sticker(foto(1200, 600), OpcionesSticker(recortar=True)).datos
    assert alfa_en(datos, (256, 5)) == 255
    assert alfa_en(datos, (5, 5)) == 255


def test_png_transparente_sigue_transparente():
    datos = crear_sticker(foto(400, 400, formato="PNG", modo="RGBA", color=(0, 0, 0, 0)), OPC).datos
    assert alfa_en(datos, (10, 10)) == 0


def test_foto_dificil_entra_en_100_kb():
    s = crear_sticker(ruido(), OPC)
    assert len(s.datos) <= 100 * 1024


def test_marca_de_agua_cambia_la_esquina():
    sin = crear_sticker(foto(600, 600), OpcionesSticker(marca_de_agua="")).datos
    con = crear_sticker(foto(600, 600), OpcionesSticker(marca_de_agua="Licha Bot")).datos
    with Image.open(io.BytesIO(sin)) as a, Image.open(io.BytesIO(con)) as b:
        esquina = (380, 470, 510, 510)
        assert a.convert("RGB").crop(esquina).tobytes() != b.convert("RGB").crop(esquina).tobytes()


def test_gif_a_sticker_animado():
    s = crear_sticker(gif(cuadros=12, duracion_ms=100), OPC)
    info = inspeccionar_webp(s.datos)
    assert s.animado and info["animado"]
    assert info["cuadros"] > 1
    assert 1100 <= info["duracion_ms"] <= 1300
    assert info["bytes"] <= 500 * 1024
    assert info["exif"]["sticker-pack-name"] == "Mi pack"


def test_gif_de_un_cuadro_es_estatico():
    s = crear_sticker(gif(cuadros=1), OPC)
    assert not s.animado


def test_video_a_sticker_animado():
    s = crear_sticker(video(segundos=2), OPC)
    info = inspeccionar_webp(s.datos)
    assert s.animado
    assert (info["ancho"], info["alto"]) == (LIENZO, LIENZO)
    assert 1800 <= info["duracion_ms"] <= 2200
    assert info["bytes"] <= 500 * 1024


def test_video_largo_se_corta():
    s = crear_sticker(video(segundos=4, fps=10, ancho=160, alto=120), OpcionesSticker(max_segundos=2))
    assert inspeccionar_webp(s.datos)["duracion_ms"] <= 2100


def test_sticker_animado_se_puede_volver_a_convertir():
    original = crear_sticker(gif(), OPC).datos
    s = crear_sticker(original, OpcionesSticker(paquete="Otro"))
    assert s.animado
    assert inspeccionar_webp(s.datos)["exif"]["sticker-pack-name"] == "Otro"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="hace falta ffmpeg para armar el video girado")
def test_video_vertical_de_celular_se_gira(tmp_path):
    apaisado = tmp_path / "a.mp4"
    girado = tmp_path / "g.mp4"
    apaisado.write_bytes(video(segundos=1, ancho=320, alto=160))
    comando = ["ffmpeg", "-loglevel", "error", "-y", "-display_rotation", "90", "-i", str(apaisado)]
    subprocess.run([*comando, "-c", "copy", str(girado)], check=True)
    datos = crear_sticker(girado.read_bytes(), OPC).datos
    # Girado queda más alto que ancho: los costados son transparentes y arriba hay imagen.
    assert alfa_en(datos, (5, 256)) == 0
    assert alfa_en(datos, (256, 5)) == 255


def test_archivo_que_no_es_media():
    with pytest.raises(ErrorSticker) as error:
        crear_sticker(b"esto no es una imagen ni un video", OPC)
    assert "No pude leer" in error.value.mensaje


def test_sticker_a_imagen():
    webp = crear_sticker(foto(400, 400, formato="PNG", modo="RGBA", color=(0, 0, 0, 0)), OPC).datos
    jpeg, animado = sticker_a_imagen(webp)
    assert not animado
    with Image.open(io.BytesIO(jpeg)) as img:
        assert img.format == "JPEG"
        assert img.getpixel((5, 5)) == (255, 255, 255)  # lo transparente queda blanco


def test_sticker_animado_a_imagen():
    _, animado = sticker_a_imagen(crear_sticker(gif(), OPC).datos)
    assert animado


def test_remuestrear_une_cuadros_repetidos():
    a, b = Image.new("RGBA", (1, 1)), Image.new("RGBA", (1, 1))
    # Dos cuadros de 1 s cada uno a 10 fps: quedan 2 cuadros de 1000 ms, no 20.
    salida = remuestrear([(a, 0.0), (b, 1.0)], 2.0, 10)
    assert [ms for _, ms in salida] == [1000, 1000]
    assert salida[0][0] is a and salida[1][0] is b


def test_exif_tiene_el_formato_de_whatsapp():
    exif = construir_exif("Pack", "Autor")
    assert exif[:4] == b"II*\x00"
    assert int.from_bytes(exif[14:18], "little") == len(exif) - 22
