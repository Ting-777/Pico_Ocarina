#pragma once
#include "song_store.h"
#include <algorithm>
#include <cassert>
#include <cstring>
#include <vector>

class RamFlash: public SongFlash {
public:
    std::vector<uint8_t> bytes=std::vector<uint8_t>(STORE_BYTES,0xff);
    int fail_at=-1, calls=0;
    size_t tear_bytes=0;
    const uint8_t* mapped() const override { return bytes.data(); }
    bool erase_sector(size_t offset) override {
        assert(offset%STORE_SECTOR_BYTES==0 && offset+STORE_SECTOR_BYTES<=bytes.size());
        bool fail=calls++==fail_at;
        size_t size=fail ? std::min(tear_bytes,STORE_SECTOR_BYTES) : STORE_SECTOR_BYTES;
        std::fill_n(bytes.begin()+offset,size,0xff); return !fail;
    }
    bool program_page(size_t offset,const uint8_t* page) override {
        assert(offset%STORE_PAGE_BYTES==0 && offset+STORE_PAGE_BYTES<=bytes.size());
        bool fail=calls++==fail_at;
        size_t size=fail ? std::min(tear_bytes,STORE_PAGE_BYTES) : STORE_PAGE_BYTES;
        for (size_t i=0;i<size;++i) {
            assert((bytes[offset+i]&page[i])==page[i]);
            bytes[offset+i]&=page[i];
        }
        return !fail;
    }
};
