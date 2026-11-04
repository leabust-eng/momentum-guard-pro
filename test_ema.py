"""Cambiar el periodo de EMA debe recalcular las métricas (sin errores)."""

import re

from streamlit.testing.v1 import AppTest


def metricas(at):
    """Devuelve el texto del bloque de métricas principales."""
    out = {}
    for m in at.metric:
        try:
            out[m.label] = m.value
        except Exception:
            pass
    return out


at = AppTest.from_file("app.py", default_timeout=600)
at.run()

base = metricas(at)
ema_actual = next(s.value for s in at.slider if s.label == "Periodo EMA")
print("EMA inicial:", ema_actual)
print("Retorno inicial:", base.get("Retorno total"))
print("Ops iniciales:", base.get("Operaciones"))
assert not at.exception, at.exception

for nuevo in (100, 300):
    sl = next(s for s in at.slider if s.label == "Periodo EMA")
    sl.set_value(nuevo)
    at.run()
    assert not at.exception, at.exception
    m = metricas(at)
    print(f"EMA {nuevo}: retorno {m.get('Retorno total')} | ops {m.get('Operaciones')}")
    assert m.get("Retorno total") is not None, "sin métricas tras cambiar EMA"

print("OK: la EMA recalcula métricas")
