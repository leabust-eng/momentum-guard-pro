"""La UI debe mostrar los dos drawdowns (equity y solo cerradas)."""

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=900)
at.run()
assert not at.exception, at.exception

labels = [m.label for m in at.metric]
print("métricas:", labels)
vals = {m.label: m.value for m in at.metric}
print("Máx. drawdown:", vals.get("Máx. drawdown"))
print("Máx. DD cerradas:", vals.get("Máx. DD cerradas"))
assert "Máx. DD cerradas" in labels
print("OK")
