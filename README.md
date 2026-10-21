# Eisenhower Matrix Widget

A lightweight, local-only Windows desktop task tracker built with Python and
PyQt6. Tasks are stored in a SQLite database on this computer; the app does not
use a network service.

## Requirements

- Windows 10 or later
- Python 3.10+
- PyQt6

Install the only third-party dependency:

```powershell
python -m pip install -r requirements.txt
```

## Run the widget

From this folder:

```powershell
python .\eisenhower_widget.py
```

The widget has a frameless, semi-transparent 2-by-2 matrix. Drag the header to
move it. Double-click a quadrant to add a task. Right-click a task to add a
subtask or rename it. Checkboxes complete tasks; completed siblings move below
incomplete siblings. Drag tasks within a quadrant to reorder siblings; the
drop indicator places them above or below another task, and tasks retain their
current hierarchy level. Drag a task to another quadrant to move it there; any
subtasks move with it. The three-line menu in the title bar has **Settings**
and **About**. Settings opens a screen with a left-side section list: **Colors**
lets you choose and persist a separate title color for each quadrant, and
**Reset** asks for confirmation before clearing all tasks and restoring default
colors. Drag the handle at the center of the matrix to resize the quadrant
columns and rows independently. The menu is at the top right, beside the close
button. The quadrant proportions are saved locally and restored next time the
widget starts.

## Desktop icon and startup

Run `setup_windows_shortcuts.ps1` once to create an **Eisenhower Matrix**
shortcut on the current user's Desktop and in the Windows Startup folder. The
Startup shortcut launches the widget when that user signs in. The script finds
`python.exe` on `PATH` by default and uses the matching `pythonw.exe`, so the
widget starts without a console window.

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\setup_windows_shortcuts.ps1
```

If the Python interpreter used to install PyQt6 is not on `PATH`, pass its full
path explicitly:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\setup_windows_shortcuts.ps1 `
  -PythonExe "C:\Path\To\Python\python.exe"
```

To remove both shortcuts:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\setup_windows_shortcuts.ps1 -Remove
```

## Local data

The database is created automatically at:

```text
%LOCALAPPDATA%\EisenhowerWidget\tasks_data.db
```

It is independent of the application folder and remains in place when the
shortcut is removed. Back up that file to preserve tasks.

## GitHub and privacy

The source code can be published to GitHub, but the task database is excluded
from version control. Do not commit personal task data.

## License

This project is licensed under the GNU General Public License, either version 3
or (at your option) any later version (GPL-3.0-or-later). See
[LICENSE](./LICENSE) for the license notice and the link to the full license
terms.
