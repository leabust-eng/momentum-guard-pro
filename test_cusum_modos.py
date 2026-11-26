"""Los dos modos de CUSUM deben coincidir con su fórmula de referencia."""

import numpy as np
import pandas as pd

from engine import Params, _cusum


def referencia(close, vol_period, drift, threshold, pending_bars, clasico):
    """Copia independiente de la lógica de Pine, para contrastar el motor."""
    # Pine: close - nz(close[1], close), o sea 0 en la primera vela.
    diff = np.zeros(len(close))
    diff[1:] = np.diff(close)
    vol = pd.Series(diff).rolling(vol_period).std(ddof=0).to_numpy(float)
    vol_adj = np.where(np.isnan(vol) | (vol == 0.0), 1e-8, vol)

    baseline = close[0]
    s_pos = s_neg = 0.0
    pending_dir = pending_age = 0
    pend = np.zeros(len(close), dtype=int)

    for i in range(len(close)):
        if i > 0 and not np.isnan(vol[i]):
            if clasico:
                dev_up = diff[i] / vol_adj[i]
                dev_down = -diff[i] / vol_adj[i]
            else:
                dev_up = (close[i] - baseline) / vol_adj[i]
                dev_down = (baseline - close[i]) / vol_adj[i]

            new_pos = max(0.0, s_pos + dev_up - drift)
            new_neg = max(0.0, s_neg + dev_down - drift)
            up = dn = False
            if new_pos > threshold:
                baseline = close[i]
                s_pos = s_neg = 0.0
                up = True
            elif new_neg > threshold:
                baseline = close[i]
                s_pos = s_neg = 0.0
                dn = True
            else:
                s_pos, s_neg = new_pos, new_neg

            if up:
                pending_dir, pending_age = 1, 0
            elif dn:
                pending_dir, pending_age = -1, 0
            elif pending_dir != 0:
                pending_age += 1
                if pending_age > pending_bars:
                    pending_dir = pending_age = 0
        pend[i] = pending_dir
    return pend


rng = np.random.default_rng(7)
precios = 100 * np.exp(np.cumsum(rng.normal(0.0, 0.002, 3000)))
df = pd.DataFrame(
    {
        "Open": precios,
        "High": precios * 1.001,
        "Low": precios * 0.999,
        "Close": precios,
        "Volume": 1.0,
    },
    index=pd.date_range("2026-01-01", periods=len(precios), freq="15min", tz="UTC"),
)

for modo, clasico in (("Clasico", True), ("Persistencia", False)):
    p = Params(
        cusum_mode=modo,
        cusum_vol_period=20,
        cusum_drift=0.25,
        cusum_threshold=3.0,
        pending_bars=3,
    )
    _, _, pend = _cusum(df, p)
    esperado = referencia(precios, 20, 0.25, 3.0, 3, clasico)
    assert np.array_equal(pend, esperado), modo
    print(f"OK CUSUM {modo}: {int((pend != 0).sum())} velas con señal pendiente")

# Los modos no pueden ser el mismo cálculo.
p_c = Params(cusum_mode="Clasico", cusum_vol_period=20, cusum_drift=0.25,
             cusum_threshold=3.0, pending_bars=3)
p_p = Params(cusum_mode="Persistencia", cusum_vol_period=20, cusum_drift=0.25,
             cusum_threshold=3.0, pending_bars=3)
_, _, a = _cusum(df, p_c)
_, _, b = _cusum(df, p_p)
assert not np.array_equal(a, b), "los dos modos dieron lo mismo"
print(f"OK modos distintos: {int((a != b).sum())} velas de diferencia")
