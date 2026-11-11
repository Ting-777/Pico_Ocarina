#pragma once
#include "pro_controller.h"

// Two distinct L+R presses for recognition/join, then A to confirm.
// Each press lasts 500 ms, with a full second released between presses.
class ControllerJoinSequence {
public:
    void start(uint64_t now) { started_at_=now; running_=true; }
    void stop() { running_=false; }
    bool active() const { return running_; }
    ControlState update(uint64_t now) {
        if (!running_) return {};
        uint64_t elapsed=now-started_at_;
        if (elapsed>=duration_us) { stop(); return {}; }
        ControlState state;
        if (elapsed<press_us || (elapsed>=second_lr_us && elapsed<second_lr_us+press_us)) {
            state.right=0x40;
            state.left=0x40;
        } else if (elapsed>=confirm_us) {
            state.right=0x08;
        }
        return state;
    }
private:
    static constexpr uint64_t press_us=500000, gap_us=1000000;
    static constexpr uint64_t second_lr_us=press_us+gap_us;
    static constexpr uint64_t confirm_us=second_lr_us+press_us+gap_us;
    static constexpr uint64_t duration_us=confirm_us+press_us;
    uint64_t started_at_=0;
    bool running_=false;
};
