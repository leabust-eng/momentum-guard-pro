"""Desglose de la fila de liquidación del panel en vivo."""

cap0 = 3000.0
lev = 3.0
pos_pct = 0.90
mm = 0.005
com = 0.0005
slip = 0.0002

entrada = 132.94   # precio de entrada del ejemplo
actual = 133.14    # precio "ahora"
liq = entrada * (1 - 1 / lev + mm)
margen = cap0 * pos_pct
nocional = margen * lev
units = nocional / entrada
costos = nocional * (2 * com + 2 * slip)

pnl_liq = units * (liq - entrada) - costos
print(f"margen usado:            {margen:,.2f} USDT")
print(f"exposición (nocional):   {nocional:,.2f} USDT  ({nocional/cap0:.2f}x el capital)")
print(f"unidades:                {units:.4f} AAVE")
print(f"precio de liquidación:   {liq:.2f}")
print(f"caída desde la entrada:  {(1 - liq/entrada)*100:.2f} %  (1/lev - mm = {(1/lev - mm)*100:.2f} %)")
print(f"caída desde el precio actual: {(1 - liq/actual)*100:.2f} %")
print(f"PnL en liquidación:      {pnl_liq:+,.2f} USDT")
print(f"% del capital:           {pnl_liq/cap0*100:+.2f} %")
print(f"equity resultante:       {cap0 + pnl_liq:,.2f} USDT")
print()
print(f"pérdida / margen:        {abs(pnl_liq)/margen*100:.2f} % del margen")
print(f"movimiento × exposición: {(1 - liq/entrada)*100:.2f}% × {nocional/cap0:.2f} = "
      f"{(1 - liq/entrada)*100*nocional/cap0:.2f}% del capital (antes de costos)")
print(f"costos ida y vuelta:     {costos:,.2f} USDT ({costos/cap0*100:.2f}% del capital)")
