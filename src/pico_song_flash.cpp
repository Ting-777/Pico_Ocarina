#include "pico_song_flash.h"
#include "usb_mode.h"
#include "pico/stdlib.h"
#include "hardware/flash.h"
#include "hardware/sync.h"
#include "tusb.h"
#include <cstring>
static_assert(SONG_FLASH_OFFSET+STORE_BYTES==2*1024*1024,"Song partition end");
static_assert(PICO_FLASH_SIZE_BYTES>=2*1024*1024,"Requires ordinary 2 MiB Pico");
const uint8_t* PicoSongFlash::mapped() const {
    return reinterpret_cast<const uint8_t*>(XIP_BASE+SONG_FLASH_OFFSET);
}
bool PicoSongFlash::erase_sector(size_t offset) {
    if (!ocarina_config_mode || offset%FLASH_SECTOR_SIZE || offset>STORE_BYTES-FLASH_SECTOR_SIZE) return false;
    // Single core only. No BOOTSEL sampling occurs in the configuration loop.
    uint32_t flags=save_and_disable_interrupts();
    flash_range_erase(SONG_FLASH_OFFSET+uint32_t(offset),FLASH_SECTOR_SIZE);
    restore_interrupts(flags);
    tud_task(); // Service USB between bounded sector erases.
    return true;
}
bool PicoSongFlash::program_page(size_t offset,const uint8_t* page) {
    if (!ocarina_config_mode || offset%FLASH_PAGE_SIZE || offset>STORE_BYTES-FLASH_PAGE_SIZE) return false;
    // SongStore always supplies a RAM page; Flash must not be read during write.
    uint32_t flags=save_and_disable_interrupts();
    flash_range_program(SONG_FLASH_OFFSET+uint32_t(offset),page,FLASH_PAGE_SIZE);
    restore_interrupts(flags);
    tud_task();
    return std::memcmp(mapped()+offset,page,FLASH_PAGE_SIZE)==0;
}
