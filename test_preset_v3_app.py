"""UI: el preset v3.0 carga el CUSUM clásico y el riesgo en ATR sin romper."""

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=1800)
at.run()
assert not at.exception, [str(e.value) for e in at.exception]

sel = [s for s in at.sidebar.selectbox if s.label == "Preset de estrategia"][0]
sel.set_value("TradingView v3.0")
at.run()
assert not at.exception, [str(e.value) for e in at.exception]

capital = [n for n in at.sidebar.number_input if n.label.startswith("Capital inicial")][0]
assert capital.value == 10_000.0, capital.value

modo = [s for s in at.sidebar.selectbox if s.label == "Modo de cálculo"][0]
assert modo.value.startswith("Clásico"), modo.value

riesgo = [s for s in at.sidebar.selectbox if s.label == "Modo de protección"][0]
assert riesgo.value == "ATR adaptativo", riesgo.value

etiquetas = {s.label: s.value for s in at.sidebar.slider}
assert etiquetas["Stop inicial (× ATR)"] == 4.5, etiquetas.get("Stop inicial (× ATR)")
assert etiquetas["Activar trailing tras ganancia (× ATR)"] == 2.5
assert "Stop inicial (%)" not in etiquetas

m = {x.label: x for x in at.metric}
usdt = float(m["Retorno total"].delta.replace(" USDT", "").replace(",", ""))
ops = int(m["Operaciones"].value.split("//")[0].strip())
# Medido al 2026-11-26 con 1× y 0,04 %: resultado plano/negativo y pocas ops.
assert -1_500 < usdt < 500, usdt
assert 10 <= ops <= 40, ops

# Volver a "Actual" restaura la lógica v2.1 que usa la app por defecto.
sel = [s for s in at.sidebar.selectbox if s.label == "Preset de estrategia"][0]
sel.set_value("Actual (por defecto)")
at.run()
assert not at.exception, [str(e.value) for e in at.exception]
modo = [s for s in at.sidebar.selectbox if s.label == "Modo de cálculo"][0]
assert modo.value == "Persistencia (v2.1)", modo.value

print("OK preset v3.0 en UI")
print(f"  {ops} ops · {m['Retorno total'].delta} · {modo.value}")
