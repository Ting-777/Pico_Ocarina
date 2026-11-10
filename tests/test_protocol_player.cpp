#include <cassert>
#include <array>
#include <vector>
#include <iostream>
#include "../src/pro_controller.h"
#include "../src/player.h"
#include "song.h"
static const SongView demo{SONG,SONG_COUNT,SONG_DURATION_US,3000000};
int main(){
 ProController c;c.reset();uint8_t out[64];
 assert(c.prepare(0,out)&&out[0]==0x81&&out[1]==1);c.sent(0);assert(!c.prepare(1,out));
 uint8_t handshake[]={0x80,2};c.receive(0,handshake,sizeof handshake);assert(c.prepare(1,out)&&out[0]==0x81&&out[1]==2);c.sent(1);
 uint8_t handshake3[]={3};c.receive(0x80,handshake3,1);assert(c.prepare(2,out)&&out[1]==3);c.sent(2);
 uint8_t mode[12]={1};mode[10]=3;mode[11]=0x30;c.receive(0,mode,12);
 assert(c.ready());assert(c.prepare(3,out)&&out[0]==0x21&&out[13]==0x80&&out[14]==3);c.sent(3);
 assert(c.prepare(11,out)&&out[0]==0x30&&out[6]==0&&out[7]==8&&out[8]==128);c.sent(11);
 // SPI address 0x603D left stick calibration; verify exact bytes and bounds.
 uint8_t spi[16]={1};spi[10]=0x10;spi[11]=0x3d;spi[12]=0x60;spi[15]=9;
 c.receive(0,spi,16);assert(c.prepare(12,out)&&out[13]==0x90&&out[19]==9&&out[20]==0xa4&&out[23]==0);c.sent(12);
 spi[15]=255;c.receive(0,spi,16);assert(c.prepare(13,out)&&out[19]==44);c.sent(13);
 for(unsigned i=0;i<16;i++)c.receive(0,spi,i); // truncated commands must be safe
 c.reset();assert(!c.ready());
 SongPlayer p;p.start(demo,0);assert(p.counting(2999999));assert(p.update(0).right==0);
 unsigned presses=0;bool wasOn=false;
 for(uint64_t t=3000000;t<=3000000+SONG_DURATION_US+1000;t+=1000){
  auto s=p.update(t);bool on=s.left||s.right;if(on&&!wasOn)presses++;wasOn=on;
 }
 assert(presses==SONG_COUNT&&!p.active());
 p.start(demo,0);p.stop();assert(p.update(4000000).right==0&&!p.active());
 auto high=fingering(89),low=fingering(86);
 assert(high.right==2&&high.left==2&&high.ly==3748);assert(low.right==2&&low.left==0&&low.ly==2048);
 unsigned endings=0;
 for(unsigned i=0;i+4<SONG_COUNT;i++){
  if(SONG[i].pitch==89){assert(SONG[i+1].pitch==86&&SONG[i+2].pitch==86&&SONG[i+3].pitch==84&&SONG[i+4].pitch==86);endings++;}
  assert(SONG[i].off>SONG[i].on&&SONG[i].off<=SONG[i+1].on-40000);
 }
 assert(endings==(SONG_FULL?3u:0u));
 // First occurrence (source bar27) must remain the LOW octave, not bar51.
 const uint8_t firstTail[5]={77,74,74,72,74};bool foundFirst=false;
 for(unsigned i=0;i+4<SONG_COUNT;i++)if(SONG[i].on==30508500){
  for(unsigned j=0;j<5;j++)assert(SONG[i+j].pitch==firstTail[j]);
  foundFirst=true;
 }
 assert(foundFirst);
 // Two independent modifiers must coexist in the same report.
 c.state=high;uint8_t start[]={0x80,4};c.receive(0,start,2);assert(c.prepare(100,out));c.sent(100);
 assert(c.prepare(108,out)&&out[0]==0x30&&out[3]==2&&out[5]==2);
 uint16_t y=uint16_t(out[7]>>4)|(uint16_t(out[8])<<4);assert(y==3748);
 std::cout<<"PASS: USB handshake, subcommands, calibration, malformed lengths, "<<SONG_COUNT<<" notes, original ending contours, independent D-pad/stick\n";
}
