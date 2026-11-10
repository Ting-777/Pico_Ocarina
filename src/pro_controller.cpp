// USB handshake/subcommands adapted from GP2040-CE (MIT).
#include "pro_controller.h"
#include "calibration.h"
#include <algorithm>
void ProController::reset(){state={};initialized=false;identified=false;sequence=0;head=count=0;lastSent=0;playerLights=0;}
static void pack(uint8_t* dst,uint16_t x,uint16_t y){dst[0]=x&255;dst[1]=((x>>8)&15)|((y&15)<<4);dst[2]=(y>>4)&255;}
void ProController::input(uint8_t out[64],uint8_t id)const{
 std::memset(out,0,64);out[0]=id;out[1]=sequence;out[2]=0x81;
 out[3]=state.right;out[4]=state.shared|0x80;out[5]=state.left;
 pack(out+6,state.lx,state.ly);pack(out+9,state.rx,state.ry);out[12]=9;
}
void ProController::identify(uint8_t out[64])const{
 std::memset(out,0,64);out[0]=0x81;out[1]=1;out[3]=3;
 const uint8_t mac[6]={0x12,0x34,0x56,0x8a,0xbb,0x7c};std::memcpy(out+4,mac,6);
}
void ProController::push(const uint8_t data[64]){if(count==8)return;std::memcpy(queue[(head+count)%8],data,64);count++;}
void ProController::receive(uint8_t id,const uint8_t* data,uint16_t size){
 if(!data||!size)return;
 uint8_t frame[65]{};uint16_t len;
 // Interrupt OUT includes the ID; SET_REPORT provides it separately.
 if(id){frame[0]=id;len=std::min<uint16_t>(size,64)+1;std::memcpy(frame+1,data,len-1);}
 else {len=std::min<uint16_t>(size,65);std::memcpy(frame,data,len);}
 uint8_t out[64]{};
 if(frame[0]==0x80&&len>=2){
  switch(frame[1]){
   case 1:identify(out);push(out);identified=true;break;
   case 2:case 3:out[0]=0x81;out[1]=frame[1];push(out);break;
   case 4:initialized=true;break; // Disable USB timeout, no ACK required.
   case 5:initialized=false;break;
   default:break;
  }
  return;
 }
 if(frame[0]!=1||len<11)return;
 uint8_t cmd=frame[10];input(out,0x21);out[13]=0x80;out[14]=cmd;
 switch(cmd){
  case 0x00:out[15]=3;break;
  case 0x01:out[13]=0x81;out[15]=3;break;
  case 0x02:{
   out[13]=0x82;const uint8_t info[12]={4,0x91,3,2,0x7c,0xbb,0x8a,0x56,0x34,0x12,1,2};
   std::memcpy(out+15,info,sizeof info);break;
  }
  case 0x03:if(len<12)return;out[15]=frame[11];if(frame[11]==0x30)initialized=true;break;
  case 0x04:out[13]=0x83;break;
  case 0x10:{
   if(len<16)return;
   uint32_t address=uint32_t(frame[11])|(uint32_t(frame[12])<<8)|(uint32_t(frame[13])<<16)|(uint32_t(frame[14])<<24);
   uint8_t n=std::min<uint8_t>(frame[15],44);out[13]=0x90;
   std::memcpy(out+15,frame+11,4);out[19]=n;std::memset(out+20,0xff,n);
   if(address>=0x6000&&address-0x6000+n<=sizeof factoryConfigData)std::memcpy(out+20,factoryConfigData+address-0x6000,n);
   else if(address>=0x8000&&address-0x8000+n<=sizeof userCalibrationData)std::memcpy(out+20,userCalibrationData+address-0x8000,n);
   break;
  }
  case 0x30:if(len<12)return;playerLights=frame[11];break;
  case 0x31:out[13]=0xb0;out[15]=playerLights;break;
  case 0x33:out[15]=3;break;
  case 0x43:if(len<13)return;out[13]=0xc0;out[15]=frame[11];out[16]=frame[12];break;
  case 0x50:out[13]=0xd0;out[15]=0x83;out[16]=6;break;
  default:break;
 }
 push(out);
}
bool ProController::prepare(uint32_t now,uint8_t out[64]){
 if(count){std::memcpy(out,queue[head],64);if(out[0]!=0x81)out[1]=sequence;preparedQueue=true;return true;}
 if(!identified){identify(out);preparedQueue=false;return true;}
 if(initialized&&uint32_t(now-lastSent)>=8){input(out,0x30);preparedQueue=false;return true;}
 return false;
}
void ProController::sent(uint32_t now){if(preparedQueue&&count){head=(head+1)%8;count--;}identified=true;lastSent=now;sequence++;}
