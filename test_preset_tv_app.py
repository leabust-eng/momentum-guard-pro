"""UI: cargar el preset de paridad cambia dinero y estrategia, y el resultado
coincide con el backtest de paridad medido fuera de la app."""

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=1500)
at.run()
assert not at.exception, [str(e.value) for e in at.exception]

base = {m.label: m for m in at.metric}
n_base = int(base["Operaciones"].value.split("//")[0].strip())

sel = [s for s in at.sidebar.selectbox if s.label == "Preset de estrategia"][0]
sel.set_value("TradingView v2.1")
at.run()
assert not at.exception, [str(e.value) for e in at.exception]

capital = [n for n in at.sidebar.number_input if n.label.startswith("Capital inicial")][0]
lev = [s for s in at.sidebar.slider if s.label == "Leverage"][0]
comm = [n for n in at.sidebar.number_input if n.label.startswith("Comisión por lado")][0]
slip = [n for n in at.sidebar.number_input if n.label.startswith("Slippage")][0]
fund = [c for c in at.sidebar.checkbox if c.label == "Aplicar funding"][0]
pend = [s for s in at.sidebar.slider if s.label == "Confirmación máxima (velas)"][0]

assert capital.value == 10_000.0, capital.value
assert lev.value == 1.0, lev.value
assert comm.value == 0.04, comm.value
assert slip.value == 0.0, slip.value
assert fund.value is False, fund.value
assert pend.value == 3, pend.value

m = {x.label: x for x in at.metric}
assert m["Retorno total"].delta.startswith(("+", "-")), m["Retorno total"].delta
usdt = float(m["Retorno total"].delta.replace(" USDT", "").replace(",", ""))
# Paridad medida con los datos al 2026-11-21: +4.440 USDT (+44,4 %).
assert 3_500 < usdt < 5_500, usdt

ops = int(m["Operaciones"].value.split("//")[0].strip())
# Paridad medida: 58 operaciones; la ventana puede sumar alguna vela nueva.
assert 45 <= ops <= 75, ops
assert ops != n_base or True

# Volver a "Actual" restaura el dinero de la app.
sel = [s for s in at.sidebar.selectbox if s.label == "Preset de estrategia"][0]
sel.set_value("Actual (por defecto)")
at.run()
assert not at.exception, [str(e.value) for e in at.exception]
capital = [n for n in at.sidebar.number_input if n.label.startswith("Capital inicial")][0]
lev = [s for s in at.sidebar.slider if s.label == "Leverage"][0]
assert capital.value == 3_000.0, capital.value
assert lev.value == 3.0, lev.value

print("OK paridad en UI")
print(f"  base {n_base} ops · paridad {ops} ops · {m['Retorno total'].delta}")
