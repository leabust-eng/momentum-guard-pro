' Lanzador oculto del vigilante (para el Programador de tareas de Windows).
' Ejecuta keep_alive.ps1 sin mostrar ninguna ventana.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Users\leabu\momentum_guard"
sh.Run "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""C:\Users\leabu\momentum_guard\keep_alive.ps1""", 0, False
