"""Regresión de UI: selector ATR vs porcentaje en el sidebar."""

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=900)
at.run()
assert not at.exception, [str(e.value) for e in at.exception]

modo = [s for s in at.sidebar.selectbox if s.label == "Unidad de la banda"][0]
assert modo.value == "ATR adaptativo", modo.value

sliders = [s.label for s in at.sidebar.slider]
assert "Distancia mínima (× ATR)" in sliders, sliders
assert "Distancia máxima (× ATR)" in sliders, sliders
assert "Distancia mínima (%)" not in sliders, sliders

ret_atr = {m.label: m.value for m in at.metric}["Retorno total"]

modo.set_value("Porcentaje fijo")
at.run()
assert not at.exception, [str(e.value) for e in at.exception]

sliders = [s.label for s in at.sidebar.slider]
assert "Distancia mínima (%)" in sliders, sliders
assert "Distancia mínima (× ATR)" not in sliders, sliders

ret_pct = {m.label: m.value for m in at.metric}["Retorno total"]
assert ret_pct != ret_atr, f"El modo no cambió el resultado: {ret_atr}"

print("OK selector banda")
print("ATR:", ret_atr, "· Pct:", ret_pct)
