#pragma once
#include "song_store.h"
class PicoSongFlash final: public SongFlash {
public:
    const uint8_t* mapped() const override;
    bool erase_sector(size_t offset) override;
    bool program_page(size_t offset,const uint8_t* page) override;
};
// Fixed final 136 KiB of the ordinary Pico's 2 MiB Flash.
constexpr uint32_t SONG_FLASH_OFFSET=0x1de000;
