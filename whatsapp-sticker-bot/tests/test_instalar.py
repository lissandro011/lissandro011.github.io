"""Pruebas del instalador guiado (la parte que no necesita internet ni Windows)."""

import pytest

import instalar


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("5491123456789", "5491123456789"),
        ("+54 9 11 2345-6789", "5491123456789"),
        ("5493512345678", "5493512345678"),
        ("34612345678", "34612345678"),  # España
    ],
)
def test_numeros_validos(entrada, esperado):
    assert instalar.validar_numero(entrada) == (esperado, None)


@pytest.mark.parametrize(
    ("entrada", "pista"),
    [
        ("011 15 2345-6789", "No empieces con 0"),
        ("541123456789", "después del 54 va un 9"),
        ("hola", "no parece válido"),
        ("123", "no parece válido"),
    ],
)
def test_numeros_invalidos_con_pista(entrada, pista):
    numero, error = instalar.validar_numero(entrada)
    assert numero is None and pista in error


def test_guardar_numero_reemplaza_la_linea():
    texto = "# comentario\nWA_PHONE_NUMBER=\nLOG_LEVEL=INFO\n"
    nuevo = instalar.guardar_numero(texto, "5491123456789")
    assert nuevo == "# comentario\nWA_PHONE_NUMBER=5491123456789\nLOG_LEVEL=INFO\n"
    assert instalar.leer_numero_actual(nuevo) == "5491123456789"
    assert instalar.guardar_numero("LOG_LEVEL=INFO", "549") == "LOG_LEVEL=INFO\nWA_PHONE_NUMBER=549\n"


def _preparar(tmp_path, monkeypatch, respuestas, env_inicial=None):
    example = tmp_path / ".env.example"
    example.write_text("# config\nWA_PHONE_NUMBER=\nLOG_FILE=data/bot.log\n", encoding="utf-8")
    env = tmp_path / ".env"
    if env_inicial is not None:
        env.write_text(env_inicial, encoding="utf-8")
    monkeypatch.setattr(instalar, "ENV_FILE", env)
    monkeypatch.setattr(instalar, "ENV_EXAMPLE", example)
    respuestas = iter(respuestas)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(respuestas))
    return env


def test_configurar_numero_crea_env_y_reintenta(tmp_path, monkeypatch, capsys):
    env = _preparar(tmp_path, monkeypatch, ["011 15 2345-6789", "5491123456789"])
    instalar.configurar_numero()
    assert instalar.leer_numero_actual(env.read_text(encoding="utf-8")) == "5491123456789"
    assert "LOG_FILE=data/bot.log" in env.read_text(encoding="utf-8")
    assert "No empieces con 0" in capsys.readouterr().out


def test_configurar_numero_enter_conserva_el_actual(tmp_path, monkeypatch):
    env = _preparar(tmp_path, monkeypatch, [""], env_inicial="WA_PHONE_NUMBER=5491100000000\n")
    instalar.configurar_numero()
    assert env.read_text(encoding="utf-8") == "WA_PHONE_NUMBER=5491100000000\n"


def test_configurar_numero_sin_teclado_no_se_cuelga(tmp_path, monkeypatch):
    env = _preparar(tmp_path, monkeypatch, [])

    def sin_teclado(_prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", sin_teclado)
    instalar.configurar_numero()
    assert instalar.leer_numero_actual(env.read_text(encoding="utf-8")) == ""
