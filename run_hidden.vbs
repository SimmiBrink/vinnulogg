' run_hidden.vbs - Ræsir Vinnulogg án þess að sýna terminal glugga
' Tvísmelltu á þessa skrá til að ræsa logger í bakgrunni

Dim WshShell
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "pythonw activity_logger.py", 0, False
Set WshShell = Nothing
