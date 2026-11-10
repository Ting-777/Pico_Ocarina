#pragma once
#include <cstddef>
#include <cstdint>

constexpr size_t MELODY_MAX_BYTES = 65536;
constexpr size_t MELODY_MAX_NOTES = 4096;
constexpr uint32_t MELODY_MAX_DURATION_US = 3600000000u;
constexpr uint32_t MELODY_RELEASE_US = 40000;
constexpr char MELODY_PROFILE[] = "oot-user-image-reference-v1";

struct SongNote { uint32_t on, off; uint8_t pitch; };
struct SongView {
    const SongNote* notes = nullptr;
    size_t count = 0;
    uint32_t duration_us = 0, countdown_us = 0;
};
struct LoadedSong {
    SongNote notes[MELODY_MAX_NOTES]{};
    size_t count = 0;
    uint32_t duration_us = 0, countdown_us = 0;
    char title[321]{}; // 80 Unicode scalar values, at most 4 UTF-8 bytes each.
    size_t title_bytes = 0;
    SongView view() const { return {notes, count, duration_us, countdown_us}; }
};
struct MelodyInfo { size_t count=0; uint32_t duration_us=0, countdown_us=0; };
enum class MelodyError {
    Ok, Size, Syntax, Utf8, Depth, DuplicateField, UnknownField, MissingField,
    Format, Version, Profile, Range, NoteCount, Pitch, Timing, Order, ReleaseGap
};
struct MelodyResult {
    MelodyError error = MelodyError::Ok;
    size_t offset = 0, note_index = size_t(-1);
    const char* field = "";
    explicit operator bool() const { return error == MelodyError::Ok; }
};
const char* melody_error_name(MelodyError error);
// Bounded, allocation-free validation. Immutable input must remain unchanged
// throughout a call and must not overlap the output object.
MelodyResult validate_melody(const char* bytes, size_t size, MelodyInfo* info=nullptr);
// Validates a first pass before writing a second pass into destination.
// Every rejection leaves destination unchanged. Call only while playback stops.
MelodyResult load_melody(const char* bytes, size_t size, LoadedSong& destination);
