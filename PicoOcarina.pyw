"""Double-click entry point for the song manager."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parent / "tools" / "midi_gui_launcher.pyw"),
               run_name="__main__")
