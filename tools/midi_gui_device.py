"""Immutable song bytes and Pico transport, shared by the GUI and native tests."""
from i18n import tr
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from melody_format import MAX_BYTES, decode_document
import upload_melody


@dataclass(frozen=True)
class SongFile:
    path: Path
    data: bytes

    @property
    def document(self):
        return decode_document(self.data)


def load_song(path):
    path = Path(path).resolve()
    with path.open("rb") as file:
        data = file.read(MAX_BYTES + 1)
    decode_document(data)
    return SongFile(path, data)


def song_summary(song):
    document = song.document
    return tr("%s\n%d 个音 · %.1f 秒 · 倒数 %.1f 秒 · %d 字节") % (
        document.get("title") or song.path.stem, len(document["notes"]),
        document["duration_us"] / 1000000, document["countdown_us"] / 1000000, len(song.data))


@dataclass(frozen=True)
class PortChoice:
    device: str
    description: str
    pico: bool

    @property
    def label(self):
        return "%s · %s%s" % (self.device, self.description, tr("（Pico配置模式）") if self.pico else "")


def require_serial():
    try:
        import serial
        if not callable(getattr(serial, "Serial", None)):
            raise ImportError("incorrect serial package")
        return serial
    except ImportError as error:
        raise RuntimeError(tr("缺少串口组件，请点击窗口下方的“安装所需组件”，或安装 tools/requirements-gui.txt")) from error


def list_ports(enumerator=None):
    if enumerator is None:
        require_serial()
        from serial.tools.list_ports import comports
        enumerator = comports
    choices = [PortChoice(str(port.device), str(port.description or tr("串口")),
                          (port.vid, port.pid) == (0xCAFE, 0x4010)) for port in enumerator()]
    return sorted(choices, key=lambda port: (not port.pico, port.device.casefold()))


@contextmanager
def connection(name, factory=None):
    name = str(name).strip()
    if not name:
        raise ValueError(tr("请选择Pico的串口，或填写COM编号"))
    factory = factory or require_serial().Serial
    try:
        with factory(name, 115200, timeout=15, write_timeout=15) as port:
            port.reset_input_buffer()
            yield port
    except OSError as error:
        raise RuntimeError(tr("串口 %s 无法使用或连接中断，请检查USB、配置模式和端口占用。\n%s") % (name, error)) from error


def upload_song(song, port_name, progress=None, factory=None):
    document = song.document
    if progress:
        progress("connect", 0, len(song.data))
    with connection(port_name, factory) as port:
        status = verified_status(upload_melody.fields(upload_melody.upload(port, song.data, progress)))
    expected = {"notes": len(document["notes"]), "duration_us": document["duration_us"],
                "countdown_us": document["countdown_us"]}
    if any(int(status.get(key, "-1")) != value for key, value in expected.items()):
        raise upload_melody.ProtocolError(tr("保存后回读的歌曲信息不匹配，请读取设备状态确认"))
    if progress:
        progress("done", len(song.data), len(song.data))
    return status


def device_status(port_name, factory=None):
    with connection(port_name, factory) as port:
        hello = upload_melody.fields(upload_melody.request(port, "HELLO"))
        if hello.get("protocol") != "1":
            raise upload_melody.ProtocolError(tr("这不是支持的Pico配置接口，请检查串口和GP21接线"))
        return verified_status(upload_melody.fields(upload_melody.request(port, "STATUS")))


def verified_status(status):
    if status.get("protocol") != "1" or status.get("saved") not in ("0", "1"):
        raise upload_melody.ProtocolError(tr("设备状态回复不完整或版本不符，无法确认是否已保存"))
    if status["saved"] == "1":
        limits = {"notes": (1, 4096), "duration_us": (1, 3600000000), "countdown_us": (0, 10000000),
                  "generation": (0, 0xffffffff), "bytes": (1, MAX_BYTES)}
        try:
            valid = status.get("schema") == "1" and all(
                low <= int(status.get(key, "-1")) <= high for key, (low, high) in limits.items())
            valid = valid and len(status.get("crc", "")) == 8 and 0 <= int(status["crc"], 16) <= 0xffffffff
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise upload_melody.ProtocolError(tr("设备保存状态字段异常，无法确认歌曲信息"))
    return status


def status_summary(status):
    if status.get("saved") != "1":
        return tr("设备尚无有效上传歌曲，正常启动时使用内置默认曲。")
    return tr("设备已保存：%s 个音 · %.1f 秒\n代次 %s · CRC %s") % (
        status.get("notes", "?"), int(status.get("duration_us", "0")) / 1000000,
        status.get("generation", "?"), status.get("crc", "?"))
