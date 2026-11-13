"""Windows MIDI sequencer adapter."""
import ctypes
import os
from pathlib import Path
import time
import uuid

class MidiPlayer:
    START_TIMEOUT = 3.0

    def __init__(self):
        self.alias = "ocarina_" + uuid.uuid4().hex
        self.opened = False
        self._api = None
        self._observed_playing = False
        self._last_active = 0.0
        self._end_ms = None

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
            raise RuntimeError("MIDI试听失败：%s（%d）" % (detail.value, error))
        return result.value.strip()

    def play(self, file, start_ms=0, end_ms=None):
        self.stop()
        start_ms = max(0, int(start_ms))
        if end_ms is not None:
            end_ms = int(end_ms)
            if end_ms <= start_ms:
                raise ValueError("试听结束必须在开始之后")
        file = str(Path(file).resolve())
        if '"' in file or "\n" in file or "\r" in file:
            raise ValueError("试听文件路径包含非法字符")
        self._command('open "%s" type sequencer alias %s' % (file, self.alias))
        self.opened = True
        self._observed_playing = False
        try:
            self._command("set %s time format milliseconds" % self.alias)
            # The sequencer can report less time than the SMF end-of-track
            # (for example it omits trailing silence). A larger play-to gives
            # MCIERR_OUTOFRANGE, so use the opened device's own bounds.
            length = int(self._command("status %s length" % self.alias))
            if length <= 0 or start_ms >= length:
                self.stop()
                return False
            self._end_ms = min(end_ms, length) if end_ms is not None else length
            self._last_active = time.monotonic()
            command = "play %s" % self.alias
            if start_ms:
                command += " from %d" % start_ms
            if self._end_ms < length:
                command += " to %d" % self._end_ms
            self._command(command)
            return True
        except Exception:
            self.stop()
            raise

    def position_ms(self):
        if not self.opened:
            return None
        return int(self._command("status %s position" % self.alias))

    def playing(self):
        if not self.opened:
            return False
        try:
            mode = self._command("status %s mode" % self.alias).lower()
        except RuntimeError:
            self.stop()
            raise
        if mode == "playing":
            self._observed_playing = True
            self._last_active = time.monotonic()
            return True
        if mode == "stopped" and self._observed_playing:
            self.stop()
            return False
        if mode in ("seeking", "not ready", "stopped", "open"):
            # MCI play is asynchronous. In particular, play-from can return
            # while still seeking; closing here cancels playback before sound.
            if mode == "stopped":
                try:
                    position = int(self._command("status %s position" % self.alias))
                except (ValueError, RuntimeError):
                    position = -1
                if self._end_ms is not None and position >= self._end_ms:
                    self.stop()
                    return False
            if time.monotonic() - self._last_active < self.START_TIMEOUT:
                return True
            self.stop()
            raise RuntimeError("Windows MIDI播放器未能启动，请检查系统音频输出后重试。")
        self.stop()
        return False

    def stop(self):
        if self.opened:
            try:
                self._command("close %s" % self.alias)
            except RuntimeError:
                pass
            finally:
                self.opened = False
                self._observed_playing = False
                self._end_ms = None
