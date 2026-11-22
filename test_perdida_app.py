"""Regresión de UI: la pérdida del periodo se muestra en USDT."""

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=1200)
at.run()
assert not at.exception, [str(e.value) for e in at.exception]

metricas = {m.label: (m.value, m.delta) for m in at.metric}

# 1. Nueva fila con los importes brutos y netos del periodo.
for etiqueta in ("Ganancia bruta", "Pérdida bruta", "Pérdida neta", "Peor operación"):
    assert etiqueta in metricas, sorted(metricas)

perdida_txt = metricas["Pérdida bruta"][0]
assert perdida_txt.endswith("USDT"), perdida_txt
perdida = float(perdida_txt.replace(" USDT", "").replace(".", "").replace(",", "."))
assert perdida < 0, perdida_txt

# La pérdida neta (solo precio) existe, está en USDT y no supera a la bruta.
neta_txt = metricas["Pérdida neta"][0]
assert neta_txt.endswith("USDT"), neta_txt
neta = float(neta_txt.replace(" USDT", "").replace(".", "").replace(",", "."))
assert neta <= 0, neta_txt
assert abs(neta) <= abs(perdida) + 0.01, (neta_txt, perdida_txt)

peor = float(
    metricas["Peor operación"][0].replace(" USDT", "").replace(".", "").replace(",", ".")
)
assert peor <= 0

# 2. Los dos drawdowns llevan su importe en USDT como delta.
for etiqueta in ("Máx. drawdown", "Máx. DD cerradas"):
    _, delta = metricas[etiqueta]
    assert delta and delta.endswith("USDT"), (etiqueta, delta)
    assert float(delta.replace(" USDT", "").replace(",", ".")) < 0, delta

print("OK perdida en UI")
print(
    "  Pérdida bruta:",
    metricas["Pérdida bruta"][0],
    "· Pérdida neta:",
    metricas["Pérdida neta"][0],
    "· Peor:",
    metricas["Peor operación"][0],
)
print("  Máx. drawdown:", metricas["Máx. drawdown"])
print("  Máx. DD cerradas:", metricas["Máx. DD cerradas"])
