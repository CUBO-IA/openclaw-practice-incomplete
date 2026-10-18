' Lanza el tick de Caregiver Agent oculto (sin ventana).
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d C:\Users\USUARIO\Desktop\openclaw && python -m caregiver.service.tick_loop --db db\caregiver_demo.db >> data\tick.log 2>&1", 0, False
