"""Check catalog coverage and formatting before packaging the desktop app."""
import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
MODULES = ("midi_gui.py", "midi_gui_range.py", "midi_gui_model.py", "midi_gui_device.py",
           "midi_gui_audio.py", "melody_format.py", "melody_timing.py", "midi_to_melody.py",
           "upload_melody.py", "midi_gui_launcher.pyw")
PRINTF = re.compile(r"%(?:\([^)]+\))?[#0+ -]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[diouxXeEfFgGcrsa%]")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate translation key: " + key)
        result[key] = value
    return result


def main():
    used, formatted = set(), set()
    for name in MODULES:
        tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and re.search(r"[\u4e00-\u9fff]", node.value):
                used.add(node.value)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr" and node.args:
                if isinstance(node.args[0], ast.Constant):
                    used.add(node.args[0].value)
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
                call = node.left
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "tr":
                    if isinstance(call.args[0], ast.Constant):
                        formatted.add(call.args[0].value)
    catalogs = {}
    for language in ("en", "ja"):
        data = json.loads((ROOT / "locales" / (language + ".json")).read_text(encoding="utf-8"),
                          object_pairs_hook=unique_object)
        missing = used - data.keys()
        if missing:
            raise ValueError(language + " missing translations: " + repr(sorted(missing)))
        for source, translation in data.items():
            if not isinstance(translation, str) or not translation:
                raise ValueError(language + " has an empty translation: " + source)
            if language == "en" and re.search(r"[\u4e00-\u9fff]", translation):
                raise ValueError("Chinese text in English translation: " + source)
            if source in formatted and PRINTF.findall(source) != PRINTF.findall(translation):
                raise ValueError(language + " format placeholders differ: " + source)
        catalogs[language] = data
    if catalogs["en"].keys() != catalogs["ja"].keys():
        raise ValueError("Catalog keys differ between English and Japanese")
    print("English / Japanese catalogs: %d messages, %d formatted messages checked" %
          (len(catalogs["en"]), len(formatted)))


if __name__ == "__main__":
    main()
