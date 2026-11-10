#pragma once
#include "melody.h"

constexpr size_t STORE_PAGE_BYTES=256, STORE_SECTOR_BYTES=4096;
constexpr size_t STORE_SLOT_BYTES=STORE_SECTOR_BYTES+MELODY_MAX_BYTES;
constexpr size_t STORE_BYTES=2*STORE_SLOT_BYTES;
// Only these relative partition offsets are accepted by the hardware adapter.
class SongFlash {
public:
    virtual ~SongFlash() = default;
    virtual const uint8_t* mapped() const = 0;
    virtual bool erase_sector(size_t offset) = 0;
    virtual bool program_page(size_t offset,const uint8_t* page) = 0;
};
uint32_t melody_crc32(const void* data,size_t size);
struct SavedSong {
    const char* bytes=nullptr;
    size_t size=0;
    uint32_t generation=0, crc=0;
    int slot=-1;
    MelodyInfo info;
    explicit operator bool() const { return slot>=0; }
};
enum class StoreError { Ok, InvalidMelody, Flash, Verify };
class SongStore {
public:
    explicit SongStore(SongFlash& flash): flash_(flash) {}
    SavedSong current() const;
    StoreError save(const char* bytes,size_t size);
private:
    SongFlash& flash_;
    SavedSong inspect(unsigned slot) const;
};
