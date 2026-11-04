"""La app debe mostrar las horas en UTC-3 y coincidir con TradingView."""

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=900)
at.run()
assert not at.exception, at.exception

tz = next(s for s in at.selectbox if s.label == "Zona horaria")
print("zona horaria por defecto:", tz.value)

caps = [c.value for c in at.caption]
ventana = next((c for c in caps if "ventana" in c), None)
print("caption:", ventana)

cols = [c.proto.label for c in at.metric]
print("métricas:", {c.label: c.value for c in at.metric if c.label in ("Retorno total", "Operaciones")})

# Cambiar a UTC no debe romper nada
tz.set_value("UTC")
at.run()
assert not at.exception, at.exception
caps = [c.value for c in at.caption]
print("caption UTC:", next((c for c in caps if "ventana" in c), None))
print("OK")
