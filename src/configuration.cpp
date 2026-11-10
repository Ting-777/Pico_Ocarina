#include "usb_mode.h"
#include "pico_song_flash.h"
#include "upload_session.h"
#include "tusb.h"
#include <cstring>

bool ocarina_config_mode=false;
namespace {
PicoSongFlash flash;
SongStore store(flash);
UploadSession upload(store);
UploadLineBuffer input;
char response[512]{};
size_t pending=0, sent=0;
bool connected=false;
}
void configuration_task() {
    bool ready=tud_cdc_connected();
    if (!ready) {
        if (connected) upload.abort();
        connected=false; pending=sent=0; input.reset(); return;
    }
    connected=true;
    if (pending) {
        size_t n=tud_cdc_write_available();
        if (n>pending-sent) n=pending-sent;
        sent+=tud_cdc_write(response+sent,uint32_t(n));
        tud_cdc_write_flush();
        if (sent<pending) return;
        pending=sent=0;
    }
    // One command per response keeps host stop-and-wait flow control bounded.
    while (tud_cdc_available()) {
        char c=char(tud_cdc_read_char());
        if (input.push(c,upload,response,sizeof response-2)) {
            size_t n=std::strlen(response); response[n++]='\n'; response[n]=0;
            pending=n; return;
        }
    }
}
