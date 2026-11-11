#include "pico/stdlib.h"
#include "hardware/sync.h"
#include "hardware/structs/ioqspi.h"
#include "hardware/structs/sio.h"
#include "bsp/board_api.h"
#include "tusb.h"
#include "pro_controller.h"
#include "player.h"
#include "controller_join.h"
#include "fallback_melody.h"
#include "usb_mode.h"
#include "pico_song_flash.h"
static LoadedSong song;
static ProController controller;
static SongPlayer player;
static ControllerJoinSequence join;
// Adapted from Raspberry Pi pico-examples picoboard/button (BSD-3-Clause).
// This is a single-core program; the flash chip select is sampled from SRAM.
bool __no_inline_not_in_flash_func(bootsel_pressed)(){
 uint32_t flags=save_and_disable_interrupts();
 hw_write_masked(&ioqspi_hw->io[1].ctrl,GPIO_OVERRIDE_LOW<<IO_QSPI_GPIO_QSPI_SS_CTRL_OEOVER_LSB,IO_QSPI_GPIO_QSPI_SS_CTRL_OEOVER_BITS);
 for(volatile int i=0;i<1000;i++){}
 bool down=!(sio_hw->gpio_hi_in&(1u<<1));
 hw_write_masked(&ioqspi_hw->io[1].ctrl,GPIO_OVERRIDE_NORMAL<<IO_QSPI_GPIO_QSPI_SS_CTRL_OEOVER_LSB,IO_QSPI_GPIO_QSPI_SS_CTRL_OEOVER_BITS);
 restore_interrupts(flags);return down;
}
extern "C" void tud_mount_cb(){controller.reset();player.stop();join.stop();}
extern "C" void tud_umount_cb(){controller.reset();player.stop();join.stop();}
extern "C" void tud_suspend_cb(bool){player.stop();join.stop();controller.state={};}
extern "C" void tud_resume_cb(){}
extern "C" uint16_t tud_hid_get_report_cb(uint8_t,uint8_t,hid_report_type_t,uint8_t*,uint16_t){return 0;}
extern "C" void tud_hid_set_report_cb(uint8_t,uint8_t id,hid_report_type_t type,uint8_t const* data,uint16_t len){if(type==HID_REPORT_TYPE_OUTPUT)controller.receive(id,data,len);}
int main(){
 board_init();gpio_init(25);gpio_set_dir(25,GPIO_OUT);gpio_init(22);gpio_set_dir(22,GPIO_IN);gpio_pull_up(22);
 gpio_init(21);gpio_set_dir(21,GPIO_IN);gpio_pull_up(21);sleep_us(100);
 ocarina_config_mode=!gpio_get(21);
 PicoSongFlash flash;SongStore store(flash);auto saved=store.current();
 // Existing full/first demo is an explicit built-in fallback, never auto-started.
 if(saved)load_melody(saved.bytes,saved.size,song);
 else load_melody(reinterpret_cast<const char*>(FALLBACK_MELODY),sizeof FALLBACK_MELODY,song);
 tusb_init();uint64_t sampleAt=0,changedAt=0,pressedAt=0;
 bool lastRaw=false,stable=false,handled=false;
 while(true){
  tud_task();uint64_t now=time_us_64();
  if(ocarina_config_mode){configuration_task();gpio_put(25,(now/150000)%2);tight_loop_contents();continue;}
  if(!tud_mounted()||tud_suspended()){player.stop();join.stop();}
  if(!controller.ready())join.stop();
  if(now>=sampleAt){
   sampleAt=now+10000;bool raw=bootsel_pressed()||!gpio_get(22);
   if(raw!=lastRaw){lastRaw=raw;changedAt=now;}
   if(raw!=stable&&now-changedAt>=20000){
    stable=raw;
    if(stable){pressedAt=now;handled=false;if(player.active()||join.active()){player.stop();join.stop();handled=true;}}
    else if(!handled&&controller.ready()&&tud_mounted()&&!tud_suspended())player.start(song.view(),now);
   }
   if(stable&&!handled&&now-pressedAt>=1000000){
    if(controller.ready()&&tud_mounted()&&!tud_suspended())join.start(now);
    handled=true;
   }
  }
  controller.state=player.update(now);
  if(join.active())controller.state=join.update(now);
  uint8_t report[64];
  if(tud_mounted()&&tud_hid_ready()&&controller.prepare(uint32_t(now/1000),report)){
   if(tud_hid_report(0,report,64))controller.sent(uint32_t(now/1000));
  }
  bool led;
  if(!controller.ready()||!tud_mounted())led=(now/500000)%2;
  else if(player.counting(now))led=(now/100000)%2;
  else if(player.active())led=(now/200000)%2;
  else led=true;
  gpio_put(25,led);tight_loop_contents();
 }
}
