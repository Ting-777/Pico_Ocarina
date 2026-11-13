"""Double-click entry point; keep dependencies private to the project."""
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / ".deps/python", ROOT / "tools"):
    if folder.is_dir():
        sys.path.insert(0, str(folder))
from i18n import tr
try:
    from midi_gui import main
    main()
except Exception as error:
    folder = ROOT / "out/gui"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "launch_error.log").write_text(traceback.format_exc(), encoding="utf-8")
    message = (tr("无法启动陶笛转换器：%s\n\n请使用带有 tkinter（tcl/tk）的 Python 3.9 或更新版本。"
               "\n详细错误已保存到：%s") % (error, folder / "launch_error.log"))
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, tr("Pico 陶笛转换器"), 0x10)
    else:
        print(message, file=sys.stderr)
