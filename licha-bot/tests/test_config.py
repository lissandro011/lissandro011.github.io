import pytest

from licha_bot.config import ARCHIVO_EJEMPLO, ErrorConfig, cargar_config, desde_dict, normalizar_numero


def test_el_ejemplo_es_valido_y_trae_los_valores_por_defecto():
    cfg = cargar_config(ARCHIVO_EJEMPLO)
    assert cfg.nombre == "Licha Bot"
    assert cfg.numero is None
    assert cfg.prefijos == ("!", ".")
    assert cfg.prefijo == "!"
    assert cfg.duenos == frozenset()
    assert cfg.stickers.paquete == "Licha Bot"
    assert cfg.stickers.automatico_en_privado is True
    assert cfg.nivel_log == "INFO"


def test_config_vacia_usa_valores_por_defecto():
    cfg = desde_dict({})
    assert cfg.nombre == "Licha Bot"
    assert cfg.stickers.max_segundos_video == 10


@pytest.mark.parametrize("crudo", ["+54 9 11 2345-6789", "5491123456789", "54 (9) 11 2345 6789"])
def test_normalizar_numero(crudo):
    assert normalizar_numero(crudo) == "5491123456789"


@pytest.mark.parametrize("crudo", ["hola", "123", "54911234567890123"])
def test_numero_invalido(crudo):
    with pytest.raises(ErrorConfig):
        normalizar_numero(crudo)


def test_numero_y_duenos():
    cfg = desde_dict({"bot": {"numero": "+54 9 11 2345-6789", "duenos": ["5491100000000", 5493410000000]}})
    assert cfg.numero == "5491123456789"
    assert cfg.duenos == {"5491100000000", "5493410000000"}


@pytest.mark.parametrize(
    "datos",
    [
        {"bot": {"responder_en_grupos": "si"}},
        {"bot": {"espera_entre_comandos": "3"}},
        {"bot": {"prefijos": []}},
        {"bot": {"prefijos": ["! !"]}},
        {"bot": {"tareas_pesadas_simultaneas": 0}},
        {"stickers": {"paquete": 5}},
        {"registro": {"nivel": "MUCHO"}},
        {"bot": "no es una sección"},
    ],
)
def test_valores_invalidos_dan_un_error_claro(datos):
    with pytest.raises(ErrorConfig):
        desde_dict(datos)


def test_archivo_con_bom_del_bloc_de_notas(tmp_path):
    archivo = tmp_path / "config.toml"
    archivo.write_bytes('﻿[bot]\nnombre = "Licha Bot"\nnumero = "5491123456789"\n'.encode())
    assert cargar_config(archivo).numero == "5491123456789"


def test_archivo_mal_escrito(tmp_path):
    archivo = tmp_path / "config.toml"
    archivo.write_text("[bot]\nnombre = Licha Bot\n", encoding="utf-8")
    with pytest.raises(ErrorConfig, match="error de formato"):
        cargar_config(archivo)


def test_seccion_propia_para_comandos_nuevos():
    cfg = desde_dict({"clima": {"ciudad": "Rosario"}})
    assert cfg.seccion("clima") == {"ciudad": "Rosario"}
    assert cfg.seccion("no_existe") == {}
