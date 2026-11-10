#pragma once
#include <cstdint>
#include <cstring>
struct ControlState {
 uint8_t right=0,shared=0,left=0;
 uint16_t lx=2048,ly=2048,rx=2048,ry=2048;
};
class ProController {
public:
 void reset();
 void receive(uint8_t report_id,const uint8_t* data,uint16_t size);
 bool prepare(uint32_t now,uint8_t out[64]);
 void sent(uint32_t now);
 bool ready()const{return initialized;}
 ControlState state;
private:
 bool initialized=false,identified=false,preparedQueue=false;
 uint8_t sequence=0,playerLights=0,head=0,count=0;
 uint32_t lastSent=0;
 uint8_t queue[8][64]{};
 void input(uint8_t out[64],uint8_t id)const;
 void identify(uint8_t out[64])const;
 void push(const uint8_t data[64]);
};
