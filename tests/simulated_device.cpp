// Native protocol/Flash process for end-to-end CLI tests; no USB emulation.
#include "ram_flash.h"
#include "upload_session.h"
#include <fstream>
#include <iostream>
#include <string>
static RamFlash flash;
int main(int argc,char** argv) {
    if (argc!=2) return 2;
    std::ifstream existing(argv[1],std::ios::binary);
    if (existing) {
        existing.read(reinterpret_cast<char*>(flash.bytes.data()),std::streamsize(flash.bytes.size()));
        if (size_t(existing.gcount())!=flash.bytes.size()) return 2;
    }
    SongStore store(flash); UploadSession upload(store); UploadLineBuffer input;
    char byte, response[512];
    while (std::cin.get(byte)) if (input.push(byte,upload,response,sizeof response)) {
        // Persist before acknowledging to model device commit response ordering.
        std::ofstream disk(argv[1],std::ios::binary|std::ios::trunc);
        disk.write(reinterpret_cast<const char*>(flash.bytes.data()),std::streamsize(flash.bytes.size()));
        disk.close(); if (!disk) return 3;
        std::cout<<response<<std::endl;
    }
}
