#pragma once
#include "song_store.h"

// Bounded ASCII request/response protocol. Each DATA line carries <=256 bytes
// as hex; USB packet boundaries have no meaning to this layer.
class UploadSession {
public:
    explicit UploadSession(SongStore& store): store_(store) {}
    // Accept one complete line without CR/LF. Always NUL-terminate response.
    void command(const char* line,char* response,size_t capacity);
    void abort();
private:
    SongStore& store_;
    char bytes_[MELODY_MAX_BYTES]{};
    size_t expected_=0, received_=0;
    uint32_t expected_crc_=0;
    bool validated_=false;
    const char* last_error_="ok";
};

// UART/CDC stream assembler shared by the device and native transport tests.
class UploadLineBuffer {
public:
    bool push(char byte,UploadSession& session,char* response,size_t capacity);
    void reset() { used_=0; bad_=false; }
private:
    char line_[560]{};
    size_t used_=0;
    bool bad_=false;
};
