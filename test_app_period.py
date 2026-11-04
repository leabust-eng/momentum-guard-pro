"""Verifica el selector de periodo de la app con AppTest (sin navegador)."""

from datetime import date

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=600)
at.run()


def dump(tag):
    print()
    print(f"== {tag} ==")
    print("excepciones:", [str(e.value) for e in at.exception])
    print(
        "selectboxes:",
        [(s.label, s.value) for s in at.sidebar.selectbox],
    )
    print(
        "date_inputs:",
        [(d.label, d.value, d.disabled) for d in at.sidebar.date_input],
    )
    print("captions:", [c.value for c in at.caption][:4])
    print("métricas:", {m.label: m.value for m in at.metric})
    cap = [c.value for c in at.caption if "ventana" in c.value]
    print("caption ventana:", cap[0] if cap else "NO ENCONTRADA")
    if at.dataframe:
        print("filas tabla ops:", len(at.dataframe[0].value))


dump("Histórico completo (default)")


def set_period(value):
    sels = [s for s in at.sidebar.selectbox if s.label == "Periodo de análisis"]
    sels[0].set_value(value)
    at.run()


set_period("Últimos 30 días")
dump("Últimos 30 días")

set_period("Personalizado")
dump("Personalizado (heredado)")

col = [x for x in at.sidebar.date_input if x.label == "Desde"][0]
col.set_value(date(2026, 10, 4))
at.run()
dump("Personalizado 2026-10-04")

set_period("Últimos 7 días")
dump("Últimos 7 días")
