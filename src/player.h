#pragma once
#include "fingering.h"
#include "melody.h"
#include <limits>

// The owner must keep the validated event buffer alive and unchanged while
// active. Loading/committing another song is only permitted after stop().
class SongPlayer {
public:
    bool start(SongView song, uint64_t now) {
        stop();
        if (!song.notes || song.count==0 || song.count>MELODY_MAX_NOTES ||
            song.duration_us==0 || song.duration_us>MELODY_MAX_DURATION_US ||
            song.countdown_us>10000000 ||
            now>std::numeric_limits<uint64_t>::max()-song.countdown_us-song.duration_us) return false;
        song_=song; origin_=now+song.countdown_us; running_=true;
        return true;
    }
    void stop() { running_=false; index_=0; }
    bool active() const { return running_; }
    bool counting(uint64_t now) const { return running_ && now<origin_; }
    ControlState update(uint64_t now) {
        if (!running_ || now<origin_) return {};
        uint64_t elapsed=now-origin_;
        if (elapsed>=song_.duration_us) { stop(); return {}; }
        while (index_<song_.count && elapsed>=song_.notes[index_].off) ++index_;
        if (index_<song_.count && elapsed>=song_.notes[index_].on)
            return fingering(song_.notes[index_].pitch);
        return {};
    }
private:
    SongView song_{};
    bool running_=false;
    uint64_t origin_=0;
    size_t index_=0;
};
