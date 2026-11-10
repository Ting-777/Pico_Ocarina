#include "song_store.h"
#include <cstring>
namespace {
constexpr uint32_t MAGIC=0x31534f50; // POS1, container v1
uint32_t read32(const uint8_t* p) {
    return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);
}
void write32(uint8_t* p,uint32_t value) {
    for (unsigned i=0;i<4;++i) p[i]=uint8_t(value>>(8*i));
}
}
uint32_t melody_crc32(const void* data,size_t size) {
    auto bytes=static_cast<const uint8_t*>(data);
    uint32_t crc=0xffffffffu;
    for (size_t i=0;i<size;++i) {
        crc^=bytes[i];
        for (unsigned bit=0;bit<8;++bit) crc=(crc>>1)^((0u-(crc&1u))&0xedb88320u);
    }
    return ~crc;
}
SavedSong SongStore::inspect(unsigned slot) const {
    const uint8_t* header=flash_.mapped()+slot*STORE_SLOT_BYTES;
    if (read32(header)!=MAGIC || read32(header+4)!=1 || read32(header+20)!=1 ||
        read32(header+24)!=melody_crc32(header,24)) return {};
    size_t size=read32(header+12);
    if (!size || size>MELODY_MAX_BYTES) return {};
    const char* bytes=reinterpret_cast<const char*>(header+STORE_SECTOR_BYTES);
    uint32_t crc=read32(header+16);
    MelodyInfo info;
    if (melody_crc32(bytes,size)!=crc || !validate_melody(bytes,size,&info)) return {};
    return {bytes,size,read32(header+8),crc,int(slot),info};
}
SavedSong SongStore::current() const {
    auto a=inspect(0), b=inspect(1);
    // Serial-number arithmetic tolerates wraparound with two adjacent saves.
    if (!a) return b;
    if (!b) return a;
    return b.generation-a.generation<0x80000000u && b.generation!=a.generation ? b : a;
}
StoreError SongStore::save(const char* bytes,size_t size) {
    if (!validate_melody(bytes,size)) return StoreError::InvalidMelody;
    // Source may be staged RAM or outside this partition, never a slot being erased.
    uintptr_t input=reinterpret_cast<uintptr_t>(bytes);
    uintptr_t base=reinterpret_cast<uintptr_t>(flash_.mapped());
    if ((input<=base && base-input<size) || (input>base && input-base<STORE_BYTES))
        return StoreError::InvalidMelody;
    auto previous=current();
    unsigned target=previous && previous.slot==0 ? 1u : 0u;
    size_t offset=target*STORE_SLOT_BYTES;
    for (size_t i=0;i<STORE_SLOT_BYTES;i+=STORE_SECTOR_BYTES)
        if (!flash_.erase_sector(offset+i)) return StoreError::Flash;
    uint8_t page[STORE_PAGE_BYTES];
    for (size_t i=0;i<size;i+=STORE_PAGE_BYTES) {
        std::memset(page,0xff,sizeof page);
        size_t n=size-i<sizeof page ? size-i : sizeof page;
        std::memcpy(page,bytes+i,n);
        if (!flash_.program_page(offset+STORE_SECTOR_BYTES+i,page)) return StoreError::Flash;
    }
    uint32_t crc=melody_crc32(bytes,size);
    if (melody_crc32(flash_.mapped()+offset+STORE_SECTOR_BYTES,size)!=crc) return StoreError::Verify;
    // Header is the atomic commit record, written only after all data verifies.
    std::memset(page,0xff,sizeof page);
    write32(page,MAGIC); write32(page+4,1);
    write32(page+8,previous ? previous.generation+1 : 1);
    write32(page+12,uint32_t(size)); write32(page+16,crc); write32(page+20,1);
    write32(page+24,melody_crc32(page,24));
    if (!flash_.program_page(offset,page)) return StoreError::Flash;
    auto saved=inspect(target);
    return saved && saved.crc==crc ? StoreError::Ok : StoreError::Verify;
}
