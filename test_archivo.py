"""El archivo propio de velas BingX debe aparecer y no romper la app."""

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=900)
at.run()
assert not at.exception, at.exception

caps = [c.value for c in at.caption]
for c in caps:
    if "ventana" in c or "Archivo propio" in c or "Inicio más antiguo" in c:
        print("caption:", c)

vals = {m.label: m.value for m in at.metric}
print("operaciones:", vals.get("Operaciones"))
print("retorno:", vals.get("Retorno total"))

assert any("Archivo propio" in c for c in caps), "no aparece el archivo propio"
print("OK")
