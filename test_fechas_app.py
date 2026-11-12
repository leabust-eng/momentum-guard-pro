"""Regresión: cambiar 'Desde' y aplicar el formulario debe recalcular la ventana."""

from datetime import date

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=900)
at.run()


def caption_ventana() -> str:
    caps = [c.value for c in at.caption if "ventana" in c.value]
    return caps[0] if caps else ""


def metricas() -> dict:
    return {m.label: m.value for m in at.metric}


assert not at.exception, [str(e.value) for e in at.exception]
base = caption_ventana()
base_ret = metricas()["Retorno total"]

# Pasar a fechas manuales.
periodo = [s for s in at.sidebar.selectbox if s.label == "Periodo de análisis"][0]
periodo.set_value("Personalizado")
at.run()
assert not at.exception, [str(e.value) for e in at.exception]

# Elegir una fecha nueva y aplicar el formulario.
desde = [d for d in at.sidebar.date_input if d.label == "Desde"][0]
desde.set_value(date(2026, 10, 1))
at.run()

botones = [b for b in at.button if "Aplicar fechas" in (b.label or "")]
assert botones, "No se encontró el botón 'Aplicar fechas'"
botones[0].click()
at.run()

assert not at.exception, [str(e.value) for e in at.exception]
nueva = caption_ventana()
assert "2026-10-01" in nueva, f"La ventana no tomó la fecha nueva: {nueva!r}"
assert nueva != base, f"La ventana no cambió: {nueva!r}"
assert metricas()["Retorno total"] != base_ret, "Las métricas no se recalcularon"

print("OK")
print("antes :", base)
print("después:", nueva)
print("Retorno antes/después:", base_ret, "/", metricas()["Retorno total"])
