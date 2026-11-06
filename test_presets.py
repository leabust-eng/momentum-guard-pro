"""El selector de presets debe cargar parámetros y símbolo coherentes."""

from streamlit.testing.v1 import AppTest


def nuevo() -> AppTest:
    at = AppTest.from_file("app.py", default_timeout=1800)
    at.run()
    assert not at.exception, at.exception
    return at


def valores(at: AppTest) -> dict:
    return {s.label: s.value for s in at.slider}


at = nuevo()
preset = next(s for s in at.selectbox if s.key == "sel_preset")
print("presets:", preset.options)

preset.set_value("OP/USDT:USDT").run()
assert not at.exception, at.exception

simbolo = next(s for s in at.selectbox if s.key == "sel_popular")
v = valores(at)
print("símbolo:", simbolo.value)
for k in [
    "Sensibilidad de señal",
    "Filtro de ruido",
    "Stop inicial (%)",
    "Activar trailing tras ganancia (%)",
    "Amplitud trailing (× ATR)",
    "Memoria ZLEMA",
    "Distancia mínima (%)",
    "Distancia máxima (%)",
]:
    print(f"  {k}: {v[k]}")

assert simbolo.value == "OP/USDT:USDT"
assert v["Sensibilidad de señal"] == 7.0
assert v["Stop inicial (%)"] == 5.0
assert v["Amplitud trailing (× ATR)"] == 4.0
assert v["Distancia mínima (%)"] == 0.5

metricas = {m.label: m.value for m in at.metric}
print("retorno con preset OP:", metricas.get("Retorno total"))

# El preset BTC debe ser frágil: se avisa en la app.
at2 = nuevo()
next(s for s in at2.selectbox if s.key == "sel_preset").set_value("BTC/USDT:USDT").run()
assert not at2.exception, at2.exception
caps = [c.value for c in at2.caption if "Walk-forward" in c.value]
print("aviso BTC:", caps[0][:90] if caps else None)
assert caps and "2/3" in caps[0]
print("OK")
