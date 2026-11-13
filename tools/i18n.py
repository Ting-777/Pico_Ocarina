"""GUI translations and the user's saved language preference."""
import json
import locale
import os
from pathlib import Path

LANGUAGES = {"en": "English", "zh_CN": "简体中文", "ja": "日本語"}
CATALOG_DIR = Path(__file__).resolve().parent / "locales"


def settings_path():
    override = os.environ.get("PICO_OCARINA_SETTINGS")
    if override:
        return Path(override)
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "PicoOcarina" / "settings.json"


def normalize_language(value):
    value = (value or "").replace("-", "_").lower()
    if value.startswith(("zh", "chinese")):
        return "zh_CN"
    if value.startswith("ja"):
        return "ja"
    return "en"


def initial_language():
    override = os.environ.get("PICO_OCARINA_LANG")
    if override:
        return normalize_language(override)
    try:
        value = json.loads(settings_path().read_text(encoding="utf-8")).get("language")
        if value in LANGUAGES:
            return value
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    try:
        system_language = locale.getlocale()[0]
    except (ValueError, TypeError):
        system_language = None
    return normalize_language(system_language)


_language = initial_language()
_catalogs = {}


def get_language():
    return _language


def set_language(language, persist=True):
    global _language
    if language not in LANGUAGES:
        raise ValueError("Unsupported language: " + str(language))
    _language = language
    if persist:
        try:
            path = settings_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps({"language": language}) + "\n", encoding="utf-8")
            temporary.replace(path)
        except OSError:
            # Keep the selected language for this session if settings are read-only.
            pass


def tr(message):
    if _language == "zh_CN":
        return message
    if _language not in _catalogs:
        _catalogs[_language] = json.loads((CATALOG_DIR / (_language + ".json")).read_text(encoding="utf-8"))
    return _catalogs[_language].get(message, message)


def ui_font():
    return {"en": "Segoe UI", "zh_CN": "Microsoft YaHei UI", "ja": "Yu Gothic UI"}[_language]


def localized_combo(parent, variable, values, **kwargs):
    """Display translated labels while keeping stable values in the form."""
    import tkinter as tk
    from tkinter import ttk
    values = tuple(values)
    display = tk.StringVar(master=parent, value=tr(variable.get()))
    combo = ttk.Combobox(parent, textvariable=display, values=[tr(value) for value in values], **kwargs)
    token = variable.trace_add("write", lambda *args: display.set(tr(variable.get())))

    def selected(event):
        index = combo.current()
        if 0 <= index < len(values):
            variable.set(values[index])

    def destroyed(event):
        if event.widget == combo:
            variable.trace_remove("write", token)

    combo.bind("<<ComboboxSelected>>", selected, add=True)
    combo.bind("<Destroy>", destroyed, add=True)
    combo._localized_display = display
    return combo
