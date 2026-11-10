#include "ram_flash.h"
#include "upload_session.h"
#include "player.h"
#include <fstream>
#include <iterator>
#include <string>
#include <cstdio>
#include <iostream>
static LoadedSong song;
static std::string read(const char* path) {
    std::ifstream file(path,std::ios::binary); assert(file);
    return std::string((std::istreambuf_iterator<char>(file)),{});
}
static std::string command(UploadSession& upload,const std::string& text) {
    char response[512]; upload.command(text.c_str(),response,sizeof response); return response;
}
static std::string hex(const std::string& bytes) {
    static const char chars[]="0123456789abcdef";
    std::string out;
    for (uint8_t c:bytes) { out+=chars[c>>4]; out+=chars[c&15]; }
    return out;
}
static std::string begin(UploadSession& upload,const std::string& bytes,uint32_t delta=0) {
    char request[80];
    std::snprintf(request,sizeof request,"BEGIN %lu %08lx",static_cast<unsigned long>(bytes.size()),
        static_cast<unsigned long>(melody_crc32(bytes.data(),bytes.size())+delta));
    return command(upload,request);
}
static void send(UploadSession& upload,const std::string& bytes) {
    assert(begin(upload,bytes)=="OK BEGIN");
    for (size_t offset=0;offset<bytes.size();offset+=256) {
        std::string data="DATA "+std::to_string(offset)+" "+hex(bytes.substr(offset,256));
        auto reply=command(upload,data); assert(reply.find("OK DATA")==0);
        assert(command(upload,data)==reply); // idempotent retransmission
    }
}
int main(int argc,char** argv) {
    assert(argc==3);
    auto a=read(argv[1]), b=read(argv[2]);
    assert(melody_crc32("123456789",9)==0xcbf43926);
    RamFlash flash; SongStore store(flash);
    assert(!store.current());
    assert(store.save(a.data(),a.size())==StoreError::Ok);
    auto saved=store.current(); assert(saved && saved.info.count==572 && saved.slot==0);
    assert(store.save("bad",3)==StoreError::InvalidMelody && store.current().crc==saved.crc);
    auto baseline=flash.bytes;
    int operations=int(STORE_SLOT_BYTES/STORE_SECTOR_BYTES+(b.size()+255)/256+1);
    for (int at=0;at<operations;++at) for (size_t tear: {size_t(0),size_t(1),size_t(27),size_t(128),size_t(256),size_t(4096)}) {
        flash.bytes=baseline; flash.calls=0; flash.fail_at=at; flash.tear_bytes=tear;
        auto error=store.save(b.data(),b.size()); assert(error==StoreError::Flash);
        SongStore rebooted(flash); auto current=rebooted.current(); assert(current);
        assert(current.crc==saved.crc || current.crc==melody_crc32(b.data(),b.size()));
        assert(std::equal(baseline.begin(),baseline.begin()+STORE_SLOT_BYTES,flash.bytes.begin()));
        assert(load_melody(current.bytes,current.size,song));
    }
    flash.bytes=baseline; flash.calls=0; flash.fail_at=-1;
    assert(store.save(b.data(),b.size())==StoreError::Ok);
    auto newer=store.current(); assert(newer.slot==1 && newer.generation==2 && newer.info.count==132);
    SongStore reboot(flash);
    auto persisted=reboot.current(); assert(persisted && persisted.crc==newer.crc);
    assert(load_melody(persisted.bytes,persisted.size,song));
    SongPlayer player; assert(player.start(song.view(),0));
    assert(!player.counting(3000000)); player.update(3000000+song.duration_us); assert(!player.active());
    // CRC and header corruption independently recover the older slot.
    flash.bytes[STORE_SLOT_BYTES+STORE_SECTOR_BYTES+10]^=1;
    assert(store.current().slot==0);
    flash.bytes=baseline;
    assert(store.save(b.data(),b.size())==StoreError::Ok);
    flash.bytes[STORE_SLOT_BYTES+8]^=1;
    assert(store.current().slot==0);
    // A valid CRC does not make a semantically invalid melody acceptable.
    flash.bytes=baseline;
    assert(store.save(b.data(),b.size())==StoreError::Ok);
    size_t payload=STORE_SLOT_BYTES+STORE_SECTOR_BYTES;
    auto version=b.find("schema_version"); assert(version!=std::string::npos);
    version=b.find(':',version)+1; while (b[version]==' ') ++version;
    flash.bytes[payload+version]='2';
    auto put32=[&](size_t offset,uint32_t value) { for (unsigned i=0;i<4;++i) flash.bytes[offset+i]=uint8_t(value>>(i*8)); };
    put32(STORE_SLOT_BYTES+16,melody_crc32(flash.bytes.data()+payload,b.size()));
    put32(STORE_SLOT_BYTES+24,melody_crc32(flash.bytes.data()+STORE_SLOT_BYTES,24));
    assert(store.current().slot==0);
    // Adjacent generation numbers still order correctly across uint32 wrap.
    flash.bytes=baseline;
    put32(8,0xffffffffu); put32(24,melody_crc32(flash.bytes.data(),24));
    assert(store.save(b.data(),b.size())==StoreError::Ok);
    assert(store.current().slot==1 && store.current().generation==0);
    assert(store.save(a.data(),a.size())==StoreError::Ok);
    assert(store.current().slot==0 && store.current().generation==1);
    // Maximum accepted file size, including trailing JSON whitespace.
    auto maximum=b; maximum.resize(MELODY_MAX_BYTES,' ');
    flash.bytes=baseline;
    assert(store.save(maximum.data(),maximum.size())==StoreError::Ok);
    assert(store.current().size==MELODY_MAX_BYTES);
    // A new store/session after power-on requires no PC stream to play.
    flash.bytes=baseline;
    UploadSession upload(store);
    assert(command(upload,"HELLO").find("OK HELLO")==0);
    assert(command(upload,"COMMIT")=="ERR not_validated");
    assert(command(upload,"BEGIN 65537 0")=="ERR begin");
    assert(begin(upload,b)=="OK BEGIN");
    assert(command(upload,"VALIDATE")=="ERR incomplete");
    assert(command(upload,"DATA 1 aa")=="ERR offset");
    assert(command(upload,"DATA 0 zz")=="ERR hex");
    assert(command(upload,"DATA 0 a")=="ERR chunk");
    assert(command(upload,"DATA 0 00").find("OK DATA")==0);
    assert(command(upload,"DATA 0 01")=="ERR retry_mismatch");
    assert(command(upload,"ABORT")=="OK ABORT");
    assert(command(upload,"DATA 0 aa")=="ERR state");
    send(upload,b); assert(command(upload,"VALIDATE")=="OK VALIDATE");
    assert(command(upload,"COMMIT").find("OK COMMIT")==0);
    assert(command(upload,"STATUS").find("notes=132")!=std::string::npos);
    auto current=store.current();
    send(upload,"{}"); assert(command(upload,"VALIDATE").find("ERR missing_field")==0);
    assert(command(upload,"COMMIT")=="ERR not_validated");
    assert(store.current().crc==current.crc);
    assert(begin(upload,"{}",1)=="OK BEGIN");
    assert(command(upload,"DATA 0 7b7d").find("OK DATA")==0);
    assert(command(upload,"VALIDATE")=="ERR crc");
    assert(store.current().crc==current.crc);
    UploadLineBuffer stream; char response[512]{};
    for (char c:std::string(1000,'x')) assert(!stream.push(c,upload,response,sizeof response));
    assert(stream.push('\n',upload,response,sizeof response) && std::string(response)=="ERR line");
    for (char c:std::string("HELLO\r\n")) stream.push(c,upload,response,sizeof response);
    assert(std::string(response).find("OK HELLO")==0);
    stream.push('\0',upload,response,sizeof response);
    assert(stream.push('\n',upload,response,sizeof response) && std::string(response)=="ERR line");
    std::cout<<"PASS: "<<operations*6<<" interrupted writes, old/new recovery, max file, CRC, upload lifecycle and framing\n";
}
