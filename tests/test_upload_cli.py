"""Run the real uploader against a native device process, then restart it."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("upload_melody", root / "tools/upload_melody.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Port:
    def __init__(self, executable, image):
        self.process = subprocess.Popen([executable, str(image)], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    def write(self, data):
        # Deliberately fragment the wire into tiny chunks.
        for at in range(0, len(data), 7):
            self.process.stdin.write(data[at:at + 7])
    def flush(self):
        self.process.stdin.flush()
    def readline(self, size):
        return self.process.stdout.readline(size)
    def close(self):
        self.process.stdin.close()
        self.process.wait(timeout=10)
        assert self.process.returncode == 0
        self.process.stdout.close()

with tempfile.TemporaryDirectory() as directory:
    image = Path(directory) / "flash.img"
    port = Port(sys.argv[1], image)
    samples = root / "examples/queens_road_east"
    try:
        for name, count in [("full", "572"), ("first", "132")]:
            data = (samples / ("melody_%s_v1_proposed.json" % name)).read_bytes()
            status = module.fields(module.upload(port, data))
            assert status["notes"] == count and status["schema"] == "1"
        before = module.fields(module.request(port, "STATUS"))
        try:
            module.upload(port, b"{}")
            raise AssertionError("invalid file was accepted")
        except module.ProtocolError as error:
            assert "missing_field" in str(error)
        after = module.fields(module.request(port, "STATUS"))
        assert before["crc"] == after["crc"] and before["generation"] == after["generation"]
    finally:
        port.close()
    port = Port(sys.argv[1], image)
    try:
        persisted = module.fields(module.request(port, "STATUS"))
        assert persisted["saved"] == "1" and persisted["notes"] == "132" and persisted["crc"] == before["crc"]
    finally:
        port.close()
print("PASS: actual CLI uploads two songs to one executable, bad-file preservation and process-restart persistence")
