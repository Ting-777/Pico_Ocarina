"""Windows MIDI sequencer adapter; no external player package."""
import ctypes
import os
from pathlib import Path
import uuid

class MidiPlayer:
    def __init__(self):
        self.alias = "ocarina_" + uuid.uuid4().hex
        self.opened = False
        self._api = None

    def _command(self, text):
        if os.name != "nt":
            raise RuntimeError("内置试听仅支持Windows；可以导出试听MIDI，用自己的播放器打开")
        if self._api is None:
            self._api = ctypes.WinDLL("winmm")
            self._api.mciSendStringW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
            self._api.mciSendStringW.restype = ctypes.c_uint
            self._api.mciGetErrorStringW.argtypes = [ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
            self._api.mciGetErrorStringW.restype = ctypes.c_int
        result = ctypes.create_unicode_buffer(512)
        error = self._api.mciSendStringW(text, result, len(result), None)
        if error:
            detail = ctypes.create_unicode_buffer(256)
            self._api.mciGetErrorStringW(error, detail, len(detail))
            raise RuntimeError("Windows MIDI试听不可用：%s（%d）。仍可正常生成和导出文件。" % (detail.value, error))
        return result.value.strip()

    def play(self, file, start_ms=0):
        self.stop()
        file = str(Path(file).resolve())
        if '"' in file or "\n" in file or "\r" in file:
            raise ValueError("试听文件路径包含非法字符")
        self._command('open "%s" type sequencer alias %s' % (file, self.alias))
        self.opened = True
        try:
            self._command("set %s time format milliseconds" % self.alias)
            self._command("play %s from %d" % (self.alias, max(0, int(start_ms))))
        except Exception:
            self.stop()
            raise

    def playing(self):
        if not self.opened:
            return False
        try:
            active = self._command("status %s mode" % self.alias) == "playing"
        except RuntimeError:
            self.stop()
            return False
        if not active:
            self.stop()
        return active

    def stop(self):
        if self.opened:
            try:
                self._command("close %s" % self.alias)
            except RuntimeError:
                pass
            finally:
                self.opened = False
