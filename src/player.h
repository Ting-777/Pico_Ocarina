#pragma once
#include "pro_controller.h"
#include "song.h"
inline ControlState fingering(uint8_t pitch){
 ControlState s;
 switch(pitch){
  case 72:s.left=0x40;s.ly=348;break; // C5: L + left stick down
  case 74:s.left=0x40;break; // D5: L
  case 76:s.left=0x40;s.ly=3748;break; // E5: L + left stick up
  case 77:s.right=0x40;break; // F5: R
  case 79:s.right=0x40;s.ly=3748;break; // G5: R + left stick up
  case 81:s.right=0x08;break; // A5: A
  case 82:s.right=0x08;s.left=2;break; // Bb5: A + D-pad up
  case 84:s.right=0x02;s.ly=348;break; // C6: X + left stick down
  case 86:s.right=0x02;break; // D6: X
  case 89:s.right=0x02;s.left=2;s.ly=3748;break; // F6: X + stick up + D-pad up
 }
 return s;
}
class SongPlayer {
public:
 void start(uint64_t now){running=true;origin=now+3000000;index=0;}
 void stop(){running=false;index=0;}
 bool active()const{return running;}
 bool counting(uint64_t now)const{return running&&now<origin;}
 ControlState update(uint64_t now){
  if(!running||now<origin)return {};
  uint64_t elapsed=now-origin;
  if(elapsed>=SONG_DURATION_US){stop();return {};}
  while(index+1<SONG_COUNT&&elapsed>=SONG[index+1].on)index++;
  if(elapsed>=SONG[index].on&&elapsed<SONG[index].off)return fingering(SONG[index].pitch);
  return {};
 }
private:
 bool running=false;
 uint64_t origin=0;
 unsigned index=0;
};
