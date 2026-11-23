"""Si engine.py cambió con el servidor corriendo, la app lo recarga sola.

Sin esto, Python conserva el módulo viejo en memoria y la página revienta con
`KeyError: 'gross_loss_price'` al faltar las métricas nuevas.
"""

from pathlib import Path

import engine
from streamlit.testing.v1 import AppTest

# Simulamos un módulo cargado antes de la última edición del archivo.
engine.LOADED_MTIME = 0.0

at = AppTest.from_file("app.py", default_timeout=1500)
at.run()
assert not at.exception, [str(e.value) for e in at.exception]

# La app detectó la diferencia y recargó el módulo: la marca quedó actualizada.
mtime = Path(engine.__file__).stat().st_mtime
assert engine.LOADED_MTIME > 0, "no se recargó engine.py"
assert abs(engine.LOADED_MTIME - mtime) < 1, (engine.LOADED_MTIME, mtime)

etiquetas = {x.label for x in at.metric}
assert "Pérdida neta" in etiquetas, sorted(etiquetas)

avisos = [w.value for w in at.warning]
assert not any("versión vieja" in a for a in avisos), avisos

print("OK recarga automática de engine.py")
print("  Pérdida neta:", {x.label: x.value for x in at.metric}["Pérdida neta"])
