"""Explicit desktop timing adjustment; firmware and JSON loading never call it."""
from copy import deepcopy
from melody_format import MelodyError, RELEASE_US, encode_document

PLAYBACK_RELEASE_US = 120000


def extend_release_gaps(document, minimum_us=PLAYBACK_RELEASE_US):
    """Insert rest without changing any note's pitch or held duration."""
    if type(minimum_us) is not int or not RELEASE_US <= minimum_us <= 1000000:
        raise MelodyError("松键间隔必须是40000–1000000微秒的整数")
    encode_document(document)
    result = deepcopy(document)
    shift = 0
    shifts = []
    previous_off = None
    for note in result["notes"]:
        on, off, pitch = note
        if previous_off is not None:
            shift += max(0, minimum_us - (on - previous_off))
        previous_off = off
        note[:] = [on + shift, off + shift, pitch]
        shifts.append(shift)
    result["duration_us"] += shift
    encode_document(result)
    return result, {"minimum_release_us": minimum_us, "added_rest_us": shift,
                    "shifted_notes": sum(value > 0 for value in shifts), "shifts_us": shifts}
