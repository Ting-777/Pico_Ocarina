#pragma once
#include "pro_controller.h"

// Fixed oot-user-image-reference-v1 profile. C6 keeps the v1.1 alternate
// (X + stick down); all other pitches use the first image variant.
inline bool lookup_fingering(uint8_t pitch, ControlState& state) {
    state = {};
    switch (pitch) {
    case 71: state.left=0x41; state.ly=348; break;
    case 72: state.left=0x40; state.ly=348; break;
    case 73: state.left=0x41; break;
    case 74: state.left=0x40; break;
    case 75: state.left=0x42; break;
    case 76: state.left=0x40; state.ly=3748; break;
    case 77: state.right=0x40; break;
    case 78: state.right=0x40; state.left=2; break;
    case 79: state.right=0x40; state.ly=3748; break;
    case 80: state.right=0x40; state.left=2; state.ly=3748; break;
    case 81: state.right=8; break;
    case 82: state.right=8; state.left=2; break;
    case 83: state.right=1; break;
    case 84: state.right=2; state.ly=348; break;
    case 85: state.right=1; state.ly=3748; break;
    case 86: state.right=2; break;
    case 87: state.right=2; state.left=2; break;
    case 88: state.right=2; state.ly=3748; break;
    case 89: state.right=2; state.left=2; state.ly=3748; break;
    default: return false;
    }
    return true;
}
inline ControlState fingering(uint8_t pitch) {
    ControlState state;
    lookup_fingering(pitch, state);
    return state;
}
