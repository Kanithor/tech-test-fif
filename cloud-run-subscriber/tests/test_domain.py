"""
Tests unitarios del dominio — sin dependencias de infraestructura.
Ejecutar con: pytest tests/
"""

import pytest
from src.domain.venta_record import VentaRecord


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def raw_valido():
    return {
        "producto": "Producto A",
        "region": "Región 1",
        "mes": "Enero 2022",
        "ventas_mensuales": 1200,
    }


# ── Tests VentaRecord ─────────────────────────────────────────────────────────

def test_parseo_mes_basico(raw_valido):
    v = VentaRecord.from_raw(raw_valido)
    assert v.mes_nombre == "Enero"
    assert v.mes_num == 1
    assert v.anno == 2022


def test_parseo_mes_septiembre():
    raw = {"producto": "P", "region": "Región 2", "mes": "Septiembre 2023", "ventas_mensuales": 500}
    v = VentaRecord.from_raw(raw)
    assert v.mes_num == 9
    assert v.anno == 2023


def test_region_code_region1(raw_valido):
    v = VentaRecord.from_raw(raw_valido)
    assert v.region_code == 0


def test_region_code_region2():
    raw = {"producto": "P", "region": "Región 2", "mes": "Enero 2022", "ventas_mensuales": 800}
    v = VentaRecord.from_raw(raw)
    assert v.region_code == 1


def test_region_code_desconocida():
    raw = {"producto": "P", "region": "Región Desconocida", "mes": "Enero 2022", "ventas_mensuales": 100}
    v = VentaRecord.from_raw(raw)
    assert v.region_code == -1


def test_ventas_mensuales_float(raw_valido):
    v = VentaRecord.from_raw(raw_valido)
    assert v.ventas_mensuales == 1200.0


def test_ventas_negativas_lanza_error():
    raw = {"producto": "P", "region": "Región 1", "mes": "Enero 2022", "ventas_mensuales": -50}
    with pytest.raises(ValueError, match="negativo"):
        VentaRecord.from_raw(raw)


def test_mes_formato_invalido_lanza_error():
    raw = {"producto": "P", "region": "Región 1", "mes": "Enero-2022", "ventas_mensuales": 100}
    with pytest.raises(ValueError, match="Formato de mes inválido"):
        VentaRecord.from_raw(raw)


def test_mes_nombre_invalido_lanza_error():
    raw = {"producto": "P", "region": "Región 1", "mes": "Octobre 2022", "ventas_mensuales": 100}
    with pytest.raises(ValueError, match="desconocido"):
        VentaRecord.from_raw(raw)


def test_campo_vacio_lanza_error():
    raw = {"producto": "", "region": "Región 1", "mes": "Enero 2022", "ventas_mensuales": 100}
    with pytest.raises(ValueError, match="'producto'"):
        VentaRecord.from_raw(raw)


def test_to_bq_row_tiene_todas_las_claves(raw_valido):
    v = VentaRecord.from_raw(raw_valido)
    fila = v.to_bq_row()
    claves_esperadas = {
        "producto", "region", "region_code",
        "mes_nombre", "mes_num", "anno",
        "ventas_mensuales", "procesado_en",
    }
    assert claves_esperadas == set(fila.keys())


# ── Tests del decoder ─────────────────────────────────────────────────────────

import base64
import json

from src.infrastructure.pubsub.pubsub_message_decoder import PubSubMessageDecoder


def _make_envelope(payload: dict) -> dict:
    data_b64 = base64.b64encode(json.dumps(payload).encode()).decode()
    return {"message": {"data": data_b64, "messageId": "123", "publishTime": "now"}}


def test_decoder_extrae_payload():
    payload = {"producto": "Producto A", "region": "Región 1",
               "mes": "Enero 2022", "ventas_mensuales": 1200}
    decoder = PubSubMessageDecoder()
    result = decoder.decode(_make_envelope(payload))
    assert result == payload


def test_decoder_sin_message_lanza_error():
    decoder = PubSubMessageDecoder()
    with pytest.raises(ValueError, match="'message'"):
        decoder.decode({"otro": "campo"})


def test_decoder_sin_data_lanza_error():
    decoder = PubSubMessageDecoder()
    with pytest.raises(ValueError, match="'data'"):
        decoder.decode({"message": {"messageId": "x"}})
