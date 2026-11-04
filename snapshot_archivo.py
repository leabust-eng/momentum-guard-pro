"""Copia el archivo vivo de velas BingX a data/snapshot/ para subirlo al repo.

Uso:
    python snapshot_archivo.py

Después:
    git add data/snapshot
    git commit -m "Actualizar archivo de velas BingX"
    git push
"""

from engine import snapshot_archive

resumen = snapshot_archive()

if not resumen:
    print("No hay velas en data/archivo/ todavía. Abrí la app y cargá datos de BingX.")
else:
    print(f"{'archivo':<34} {'velas':>9}  {'desde':<17} {'hasta'}")
    for r in resumen:
        print(
            f"{r['archivo']:<34} {r['velas']:>9,}  "
            f"{r['desde']:%Y-%m-%d %H:%M}  {r['hasta']:%Y-%m-%d %H:%M}"
        )
    print("\nListo. Ahora: git add data/snapshot && git commit -m 'Actualizar archivo BingX' && git push")
