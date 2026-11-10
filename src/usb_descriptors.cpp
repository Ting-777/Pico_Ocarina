#include "tusb.h"
#include "SwitchProDescriptors.h"
#include <cstring>
static_assert(sizeof(switch_pro_report_descriptor)==203,"HID descriptor length");
extern "C" uint8_t const* tud_descriptor_device_cb(){return switch_pro_device_descriptor;}
extern "C" uint8_t const* tud_hid_descriptor_report_cb(uint8_t){return switch_pro_report_descriptor;}
extern "C" uint8_t const* tud_descriptor_configuration_cb(uint8_t){return switch_pro_configuration_descriptor;}
extern "C" uint16_t const* tud_descriptor_string_cb(uint8_t index,uint16_t){
 static uint16_t out[33];if(index==0){out[0]=0x0304;out[1]=0x0409;return out;}
 const char* values[]={nullptr,"Pico Ocarina","Pro Controller","QRE-PICO-0001"};
 if(index>=4)return nullptr;
 size_t n=std::strlen(values[index]);if(n>32)n=32;
 for(size_t i=0;i<n;i++)out[i+1]=uint8_t(values[index][i]);
 out[0]=uint16_t(0x0300|(n*2+2));return out;
}
