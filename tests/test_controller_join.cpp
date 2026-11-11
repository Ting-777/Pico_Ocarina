#include <array>
#include <cassert>
#include <iostream>
#include <vector>
#include "controller_join.h"

static void expect(const ControlState& state, uint8_t right, uint8_t left) {
    assert(state.right==right && state.left==left && state.shared==0);
    assert(state.lx==2048 && state.ly==2048 && state.rx==2048 && state.ry==2048);
}

static void boundaries(uint64_t origin) {
    ControllerJoinSequence join;
    expect(join.update(origin),0,0);
    join.start(origin);
    for (uint64_t offset : {0,499999}) expect(join.update(origin+offset),0x40,0x40);
    for (uint64_t offset : {500000,1499999}) expect(join.update(origin+offset),0,0);
    for (uint64_t offset : {1500000,1999999}) expect(join.update(origin+offset),0x40,0x40);
    for (uint64_t offset : {2000000,2999999}) expect(join.update(origin+offset),0,0);
    for (uint64_t offset : {3000000,3499999}) expect(join.update(origin+offset),0x08,0);
    assert(join.active());
    expect(join.update(origin+3500000),0,0);
    assert(!join.active());
    expect(join.update(origin+10000000),0,0);
}

int main() {
    boundaries(0);
    boundaries((uint64_t{1}<<32)-250000);

    // Check actual 8 ms Pro reports: exactly L+R, release, L+R, release,
    // A, release, with neutral sticks and no other buttons throughout.
    ProController controller;
    controller.reset();
    uint8_t report[64];
    assert(controller.prepare(0,report));
    controller.sent(0);
    const uint8_t initialize[]={0x80,4};
    controller.receive(0,initialize,sizeof initialize);
    ControllerJoinSequence join;
    join.start(100000);
    std::vector<std::array<uint8_t,2>> transitions;
    unsigned lr_reports=0, a_reports=0;
    for (uint64_t now=100000; now<=3700000; now+=8000) {
        controller.state=join.update(now);
        assert(controller.prepare(uint32_t(now/1000),report));
        assert(report[0]==0x30 && report[4]==0x80);
        expect(controller.state,report[3],report[5]);
        assert(report[6]==0 && report[7]==8 && report[8]==128);
        assert(report[9]==0 && report[10]==8 && report[11]==128);
        std::array<uint8_t,2> buttons={report[3],report[5]};
        if (transitions.empty() || transitions.back()!=buttons) transitions.push_back(buttons);
        if (report[3]==0x40) ++lr_reports;
        if (report[3]==0x08) ++a_reports;
        controller.sent(uint32_t(now/1000));
    }
    const std::vector<std::array<uint8_t,2>> expected={
        {0x40,0x40},{0,0},{0x40,0x40},{0,0},{0x08,0},{0,0}};
    assert(transitions==expected && lr_reports==125 && a_reports==63 && !join.active());

    // Cancel during every press/wait (used for button, disconnect, suspend),
    // and ensure no later A leaks out before an explicit new start.
    for (uint64_t offset : {0,700000,1700000,2500000,3200000}) {
        join.start(100);
        join.update(100+offset);
        join.stop();
        expect(join.update(3500100),0,0);
        assert(!join.active());
        join.start(4000100);
        expect(join.update(4000100),0x40,0x40);
    }
    // A delayed loop must locate the current step without replaying old keys.
    join.start(0);
    expect(join.update(2700000),0,0);
    expect(join.update(3100000),0x08,0);
    expect(join.update(9000000),0,0);
    assert(!join.active());
    std::cout<<"PASS: L+R, 1 s release, L+R, 1 s release, A; reports, timing, cancel, 64-bit clock\n";
}
