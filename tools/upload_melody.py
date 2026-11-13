"""Upload a melody file to explicit Pico configuration mode (Windows COM port)."""
from i18n import tr
import argparse
import binascii
from pathlib import Path
import sys

MAX_BYTES = 65536

class ProtocolError(RuntimeError):
    pass

def request(port, command):
    port.write((command + "\n").encode("ascii"))
    port.flush()
    raw = port.readline(513)
    if not raw.endswith(b"\n") or len(raw) > 512:
        raise ProtocolError(tr("设备回复超时或长度异常；请读取设备状态确认是否已保存"))
    try:
        reply = raw.decode("ascii").strip()
    except UnicodeError as error:
        raise ProtocolError(tr("设备回复无法识别，请确认选择了Pico配置模式的串口")) from error
    if not reply.startswith("OK "):
        raise ProtocolError(reply)
    if reply.split()[1] != command.split()[0]:
        raise ProtocolError(tr("回复与请求不匹配: ") + reply)
    return reply

def fields(reply):
    return dict(part.split("=", 1) for part in reply.split()[2:] if "=" in part)

def upload(port, data, progress=None):
    if not 0 < len(data) <= MAX_BYTES:
        raise ValueError(tr("文件必须为 1–65536 字节"))
    # Device validation is authoritative; no Python float/schema conversion.
    crc = binascii.crc32(data) & 0xffffffff
    def report(stage, received=0):
        if progress:
            progress(stage, received, len(data))
    report("handshake")
    hello = fields(request(port, "HELLO"))
    if hello.get("protocol") != "1":
        raise ProtocolError(tr("不支持的设备协议版本"))
    request(port, "BEGIN %d %08x" % (len(data), crc))
    report("transfer")
    for offset in range(0, len(data), 256):
        reply = fields(request(port, "DATA %d %s" % (offset, data[offset:offset + 256].hex())))
        if int(reply.get("received", "-1")) != min(offset + 256, len(data)):
            raise ProtocolError(tr("设备接收偏移不匹配"))
        report("transfer", int(reply["received"]))
    report("validate", len(data))
    request(port, "VALIDATE")
    report("commit", len(data))
    committed = fields(request(port, "COMMIT"))
    if int(committed.get("bytes", "-1")) != len(data) or int(committed.get("crc", "-1"), 16) != crc:
        raise ProtocolError(tr("提交摘要不匹配"))
    report("verify", len(data))
    status = request(port, "STATUS")
    saved = fields(status)
    if (saved.get("saved") != "1" or int(saved.get("bytes", "-1")) != len(data)
            or int(saved.get("crc", "-1"), 16) != crc
            or saved.get("generation") != committed.get("generation")):
        raise ProtocolError(tr("提交后回读摘要不匹配"))
    return status

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", type=Path)
    parser.add_argument("--port", required=True, help=tr("例如 COM5"))
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if (args.file is None) == (not args.status):
        parser.error(tr("提供歌曲文件，或仅使用 --status"))
    try:
        import serial
        # Stop-and-wait accommodates sector erase latency without USB flooding.
        with serial.Serial(args.port, 115200, timeout=15, write_timeout=15) as port:
            port.reset_input_buffer()
            if args.status:
                print(request(port, "STATUS"))
            else:
                with args.file.open("rb") as file:
                    data = file.read(MAX_BYTES + 1)
                print(upload(port, data))
                print(tr("已保存。移除 GP21 接地线，断电后接 Switch；短按 BOOTSEL 播放。"))
    except (OSError, ValueError, ProtocolError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ImportError:
        print(tr("请先安装 pyserial：python -m pip install pyserial"), file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
