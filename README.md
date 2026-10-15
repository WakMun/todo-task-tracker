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
incomplete siblings. Use the three-line menu in the title bar to choose and
persist a separate title color for each quadrant, reset all tasks and settings,
or view the About information. The settings menu is at the top right, beside
the close button. Reset requires confirmation and cannot be undone.

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

This project is licensed under the GNU General Public License version 3.0 only
(GPL-3.0-only). See [LICENSE](./LICENSE) for the license notice and the link to
the full license terms.
