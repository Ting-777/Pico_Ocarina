#include "tusb.h"
#include "SwitchProDescriptors.h"
#include <cstring>
#include "usb_mode.h"
// Development CDC identity, exposed only in the explicit configuration mode.
static const tusb_desc_device_t config_device={
 sizeof(tusb_desc_device_t), TUSB_DESC_DEVICE, 0x0200,
 TUSB_CLASS_MISC, MISC_SUBCLASS_COMMON, MISC_PROTOCOL_IAD,
 CFG_TUD_ENDPOINT0_SIZE, 0xcafe, 0x4010, 0x0100, 1, 2, 3, 1
};
static const uint8_t config_descriptor[]={
 TUD_CONFIG_DESCRIPTOR(1,2,0,TUD_CONFIG_DESC_LEN+TUD_CDC_DESC_LEN,0,100),
 TUD_CDC_DESCRIPTOR(0,0,0x81,8,0x02,0x82,64)
};

static_assert(sizeof(switch_pro_report_descriptor)==203,"HID descriptor length");
extern "C" uint8_t const* tud_descriptor_device_cb(){return ocarina_config_mode ? reinterpret_cast<const uint8_t*>(&config_device) : switch_pro_device_descriptor;}
extern "C" uint8_t const* tud_hid_descriptor_report_cb(uint8_t){return switch_pro_report_descriptor;}
extern "C" uint8_t const* tud_descriptor_configuration_cb(uint8_t){return ocarina_config_mode ? config_descriptor : switch_pro_configuration_descriptor;}
extern "C" uint16_t const* tud_descriptor_string_cb(uint8_t index,uint16_t){
 static uint16_t out[33];if(index==0){out[0]=0x0304;out[1]=0x0409;return out;}
 const char* values[]={nullptr,"Pico Ocarina","Pro Controller","QRE-PICO-0001"};
 if(index>=4)return nullptr;
 const char* value=(ocarina_config_mode&&index==2)?"Pico Ocarina Config":values[index];
 size_t n=std::strlen(value);if(n>32)n=32;
 for(size_t i=0;i<n;i++)out[i+1]=uint8_t(value[i]);
 out[0]=uint16_t(0x0300|(n*2+2));return out;
}
