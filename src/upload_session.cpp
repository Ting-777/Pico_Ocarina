#include "upload_session.h"
#include <cstdio>
#include <cstring>
#include <limits>
namespace {
bool space(char c) { return c==' ' || c=='\t'; }
void spaces(const char*& p) { while (space(*p)) ++p; }
bool number(const char*& p,uint32_t& value,unsigned base=10) {
    spaces(p); value=0; bool any=false;
    while (*p && !space(*p)) {
        unsigned digit=99; char c=*p++;
        if (c>='0' && c<='9') digit=unsigned(c-'0');
        if (c>='a' && c<='f') digit=unsigned(c-'a'+10);
        if (c>='A' && c<='F') digit=unsigned(c-'A'+10);
        if (digit>=base || value>(std::numeric_limits<uint32_t>::max()-digit)/base) return false;
        value=value*base+digit; any=true;
    }
    return any;
}
bool end(const char* p) { spaces(p); return *p==0; }
unsigned hex(char c) {
    if (c>='0' && c<='9') return unsigned(c-'0');
    if (c>='a' && c<='f') return unsigned(c-'a'+10);
    if (c>='A' && c<='F') return unsigned(c-'A'+10);
    return 16;
}
}
void UploadSession::abort() { expected_=received_=0; expected_crc_=0; validated_=false; }
void UploadSession::command(const char* line,char* response,size_t capacity) {
    auto error=[&](const char* code) { last_error_=code; std::snprintf(response,capacity,"ERR %s",code); };
    char op[16]; size_t n=0;
    const char* p=line; spaces(p);
    while (*p && !space(*p)) {
        if (n+1==sizeof op) { error("command"); return; }
        op[n++]=*p++;
    }
    op[n]=0;
    if (std::strcmp(op,"HELLO")==0 && end(p)) {
        std::snprintf(response,capacity,"OK HELLO protocol=1 max_bytes=65536 chunk=256"); return;
    }
    if (std::strcmp(op,"STATUS")==0 && end(p)) {
        auto saved=store_.current();
        std::snprintf(response,capacity,"OK STATUS protocol=1 saved=%u schema=%u generation=%lu bytes=%lu crc=%08lx notes=%lu duration_us=%lu countdown_us=%lu received=%lu validated=%u last_error=%s",
            unsigned(bool(saved)),saved?1u:0u,static_cast<unsigned long>(saved.generation),
            static_cast<unsigned long>(saved.size),static_cast<unsigned long>(saved.crc),
            static_cast<unsigned long>(saved.info.count),static_cast<unsigned long>(saved.info.duration_us),
            static_cast<unsigned long>(saved.info.countdown_us),static_cast<unsigned long>(received_),unsigned(validated_),last_error_);
        return;
    }
    if (std::strcmp(op,"ABORT")==0 && end(p)) {
        abort(); last_error_="ok"; std::snprintf(response,capacity,"OK ABORT"); return;
    }
    if (std::strcmp(op,"BEGIN")==0) {
        uint32_t size=0, crc=0;
        if (!number(p,size) || !number(p,crc,16) || !end(p) || !size || size>sizeof bytes_) {
            error("begin"); return;
        }
        abort(); expected_=size; expected_crc_=crc; last_error_="ok";
        std::snprintf(response,capacity,"OK BEGIN"); return;
    }
    if (std::strcmp(op,"DATA")==0) {
        uint32_t offset=0;
        if (!expected_ || !number(p,offset)) { error("state"); return; }
        spaces(p); const char* payload=p; while (*p && !space(*p)) ++p;
        size_t length=size_t(p-payload);
        if (!end(p) || !length || (length&1) || length>512) { error("chunk"); return; }
        size_t size=length/2;
        if (offset>received_ || size>expected_ || offset>expected_-size ||
            (offset<received_ && size>received_-offset)) { error("offset"); return; }
        for (size_t i=0;i<length;++i) if (hex(payload[i])==16) { error("hex"); return; }
        if (offset<received_) {
            for (size_t i=0;i<size;++i) {
                char byte=char((hex(payload[2*i])<<4)|hex(payload[2*i+1]));
                if (bytes_[offset+i]!=byte) { error("retry_mismatch"); return; }
            }
        } else {
            for (size_t i=0;i<size;++i) bytes_[offset+i]=char((hex(payload[2*i])<<4)|hex(payload[2*i+1]));
            received_+=size; validated_=false;
        }
        std::snprintf(response,capacity,"OK DATA received=%lu",static_cast<unsigned long>(received_)); return;
    }
    if (std::strcmp(op,"VALIDATE")==0 && end(p)) {
        validated_=false;
        if (!expected_ || received_!=expected_) { error("incomplete"); return; }
        if (melody_crc32(bytes_,received_)!=expected_crc_) { error("crc"); return; }
        auto result=validate_melody(bytes_,received_);
        if (!result) {
            last_error_=melody_error_name(result.error);
            std::snprintf(response,capacity,"ERR %s field=%s offset=%lu note=%lu",last_error_,result.field,
                static_cast<unsigned long>(result.offset),static_cast<unsigned long>(result.note_index));
            return;
        }
        validated_=true; last_error_="ok";
        std::snprintf(response,capacity,"OK VALIDATE"); return;
    }
    if (std::strcmp(op,"COMMIT")==0 && end(p)) {
        if (!validated_) { error("not_validated"); return; }
        auto result=store_.save(bytes_,received_);
        if (result!=StoreError::Ok) { error(result==StoreError::InvalidMelody?"melody":"flash"); return; }
        auto saved=store_.current();
        std::snprintf(response,capacity,"OK COMMIT generation=%lu bytes=%lu crc=%08lx",
            static_cast<unsigned long>(saved.generation),static_cast<unsigned long>(saved.size),
            static_cast<unsigned long>(saved.crc));
        abort(); last_error_="ok"; return;
    }
    error("command");
}

bool UploadLineBuffer::push(char byte,UploadSession& session,char* response,size_t capacity) {
    if (byte=='\n') {
        if (bad_) std::snprintf(response,capacity,"ERR line");
        else { line_[used_]=0; session.command(line_,response,capacity); }
        reset(); return true;
    }
    if (byte=='\r') return false;
    if (byte<32 || byte>126 || used_+1>=sizeof line_) bad_=true;
    if (!bad_) line_[used_++]=byte;
    return false;
}
