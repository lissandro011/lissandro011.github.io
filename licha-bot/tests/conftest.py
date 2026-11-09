"""Utilidades para los tests: arman fotos, GIFs y videos de prueba sin internet ni WhatsApp."""

from __future__ import annotations

import io
import sys
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def foto(ancho: int = 800, alto: int = 600, formato: str = "JPEG", modo: str = "RGB", color=(30, 120, 200)) -> bytes:
    img = Image.new(modo, (ancho, alto), color)
    ImageDraw.Draw(img).ellipse((ancho // 4, alto // 4, ancho * 3 // 4, alto * 3 // 4), fill=(250, 200, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format=formato)
    return buf.getvalue()


def ruido(ancho: int = 1024, alto: int = 1024) -> bytes:
    """Foto muy difícil de comprimir (ruido puro)."""
    import os

    img = Image.frombytes("RGB", (ancho, alto), os.urandom(ancho * alto * 3))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def gif(cuadros: int = 10, duracion_ms: int = 100, lado: int = 200) -> bytes:
    imagenes = []
    for i in range(cuadros):
        img = Image.new("RGB", (lado, lado), (i * 20 % 256, 80, 160))
        ImageDraw.Draw(img).rectangle((i * 5, i * 5, i * 5 + 40, i * 5 + 40), fill=(255, 255, 255))
        imagenes.append(img)
    buf = io.BytesIO()
    imagenes[0].save(buf, format="GIF", save_all=True, append_images=imagenes[1:], duration=duracion_ms, loop=0)
    return buf.getvalue()


def video(segundos: float = 2.0, fps: int = 24, ancho: int = 320, alto: int = 240) -> bytes:
    """MP4 generado con PyAV (códec mpeg4, que viene en cualquier instalación)."""
    import av

    buf = io.BytesIO()
    with av.open(buf, mode="w", format="mp4") as contenedor:
        pista = contenedor.add_stream("mpeg4", rate=fps)
        pista.width, pista.height, pista.pix_fmt = ancho, alto, "yuv420p"
        pista.codec_context.time_base = Fraction(1, fps)
        for i in range(int(segundos * fps)):
            img = Image.new("RGB", (ancho, alto), (i * 7 % 256, 100, 200))
            ImageDraw.Draw(img).rectangle((i % ancho, 10, i % ancho + 30, 60), fill=(255, 255, 0))
            frame = av.VideoFrame.from_image(img)
            frame.pts = i
            for paquete in pista.encode(frame):
                contenedor.mux(paquete)
        for paquete in pista.encode():
            contenedor.mux(paquete)
    return buf.getvalue()
