"""Panel de impacto en el capital: 3000 USDT a 3x."""

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=900)
at.run()
assert not at.exception, at.exception

vals = {m.label: m.value for m in at.metric}
print("capital inicial:", at.number_input[0].value)
print("leverage:", next(s.value for s in at.slider if s.label == "Leverage"))
for k in ("Margen usado", "Exposición (nocional)", "Cada 1% de precio", "Máx. drawdown", "Máx. DD cerradas"):
    print(f"  {k}: {vals.get(k)}")

for i, d in enumerate(at.dataframe):
    print(f"\ntabla {i}:")
    print(d.value.to_string(index=False))
print("\ncaptions:")
for c in at.caption:
    if "cada 1%" in c.value or "stop inicial" in c.value:
        print(" ", c.value)
print("OK")
