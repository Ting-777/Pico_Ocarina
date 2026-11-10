#include "melody.h"
#include "player.h"
#include "song.h"
#include <cassert>
#include <cstring>
#include <fstream>
#include <iterator>
#include <iostream>
#include <limits>
#include <string>

static LoadedSong loaded;
static std::string document(const std::string& notes="[[0,100000,81]]",
                            const std::string& extra="") {
    return "{\"format\":\"pico-ocarina-melody\",\"schema_version\":1,"
           "\"fingering_profile\":\"oot-user-image-reference-v1\","
           "\"countdown_us\":0,\"duration_us\":3600000000,\"notes\":"+notes+extra+"}";
}
static std::string replace(std::string s, const std::string& from, const std::string& to) {
    auto p=s.find(from); assert(p!=std::string::npos); s.replace(p,from.size(),to); return s;
}
static bool neutral(ControlState s) {
    return s.right==0 && s.shared==0 && s.left==0 &&
           s.lx==2048 && s.ly==2048 && s.rx==2048 && s.ry==2048;
}
static void rejects(const std::string& text, MelodyError error) {
    unsigned char before[sizeof loaded]; std::memcpy(before,&loaded,sizeof loaded);
    auto count=loaded.count; auto first=loaded.notes[0]; auto duration=loaded.duration_us;
    auto result=load_melody(text.data(),text.size(),loaded);
    assert(!result && result.error==error);
    assert(std::memcmp(before,&loaded,sizeof loaded)==0);
    assert(loaded.count==count && loaded.duration_us==duration);
    assert(loaded.notes[0].on==first.on && loaded.notes[0].off==first.off && loaded.notes[0].pitch==first.pitch);
}
int main(int argc,char** argv) {
    assert(argc==2);
    std::ifstream file(argv[1],std::ios::binary);
    assert(file);
    std::string sample((std::istreambuf_iterator<char>(file)),{});
    assert(load_melody(sample.data(),sample.size(),loaded));
    assert(loaded.count==SONG_COUNT && loaded.duration_us==SONG_DURATION_US && loaded.countdown_us==3000000);
    for (size_t i=0;i<loaded.count;++i) {
        assert(loaded.notes[i].on==SONG[i].on && loaded.notes[i].off==SONG[i].off && loaded.notes[i].pitch==SONG[i].pitch);
    }
    // Every on/off deadline and its two neighbours, including early rest.
    SongPlayer p;
    const uint64_t now=uint64_t(std::numeric_limits<uint32_t>::max())+12345;
    assert(p.start(loaded.view(),now));
    assert(neutral(p.update(now)) && p.counting(now+2999999));
    for (size_t i=0;i<loaded.count;++i) {
        auto n=loaded.notes[i]; auto base=now+loaded.countdown_us;
        if (n.on) assert(neutral(p.update(base+n.on-1)));
        auto actual=p.update(base+n.on), expected=fingering(n.pitch);
        assert(actual.right==expected.right && actual.left==expected.left && actual.ly==expected.ly);
        assert(!neutral(p.update(base+n.off-1)));
        assert(neutral(p.update(base+n.off)));
        assert(neutral(p.update(base+n.off+1)));
    }
    assert(neutral(p.update(now+loaded.countdown_us+loaded.duration_us)) && !p.active());
    assert(p.start(loaded.view(),now)); p.stop(); assert(neutral(p.update(now+4000000)));
    assert(!p.start({},now) && neutral(p.update(now)));
    assert(!p.start(loaded.view(),std::numeric_limits<uint64_t>::max()));

    const auto valid=document();
    assert(load_melody(valid.data(),valid.size(),loaded));
    rejects("",MelodyError::Size);
    rejects(std::string(65537,' '),MelodyError::Size);
    rejects(valid+"x",MelodyError::Syntax);
    rejects(replace(valid,"\"schema_version\":1","\"schema_version\":2"),MelodyError::Version);
    rejects(replace(valid,"pico-ocarina-melody","wrong"),MelodyError::Format);
    rejects(replace(valid,MELODY_PROFILE,"unknown"),MelodyError::Profile);
    rejects(document("[]"),MelodyError::NoteCount);
    rejects(document("[[0,100000,70]]"),MelodyError::Pitch);
    rejects(document("[[0,100000,90]]"),MelodyError::Pitch);
    rejects(document("[[0,100000,256]]"),MelodyError::Pitch);
    rejects(document("[[1,1,81]]"),MelodyError::Timing);
    rejects(document("[[10,1,81]]"),MelodyError::Timing);
    rejects(document("[[0,3600000001,81]]"),MelodyError::Timing);
    rejects(replace(valid,"3600000000","1"),MelodyError::Timing);
    rejects(document("[[0,100000,81],[0,100001,81]]"),MelodyError::Order);
    rejects(document("[[200000,300000,81],[0,100000,81]]"),MelodyError::Order);
    rejects(document("[[0,100000,81],[99999,200000,81]]"),MelodyError::ReleaseGap);
    rejects(document("[[0,100000,81],[139999,200000,81]]"),MelodyError::ReleaseGap);
    assert(validate_melody(document("[[0,100000,81],[140000,200000,81]]").data(),document("[[0,100000,81],[140000,200000,81]]").size()));
    rejects(document("[[-1,100000,81]]"),MelodyError::Syntax);
    rejects(document("[[0.0,100000,81]]"),MelodyError::Syntax);
    rejects(document("[[0,100000,8.1e1]]"),MelodyError::Syntax);
    rejects(document("[[00,100000,81]]"),MelodyError::Syntax);
    rejects(document("[[0,4294967296,81]]"),MelodyError::Range);
    rejects(document("[[0,100000,\"81\"]]"),MelodyError::Syntax);
    rejects(document("[[0,100000,81,1]]"),MelodyError::Syntax);
    rejects(document("[[0,100000,81],]"),MelodyError::Syntax);
    rejects(document("[[0,100000,81]]",",\"typo\":1"),MelodyError::UnknownField);
    rejects(document("[[0,100000,81]]",",\"countdown_us\":0"),MelodyError::DuplicateField);
    rejects(replace(valid,"\"countdown_us\":0,",""),MelodyError::MissingField);
    rejects(replace(valid,"\"countdown_us\":0","\"countdown_us\":10000001"),MelodyError::Range);
    rejects(document("[[0,100000,81]]",",\"metadata\":[]"),MelodyError::Syntax);
    rejects(document("[[0,100000,81]]",",\"title\":\""+std::string(81,'a')+"\""),MelodyError::Range);
    rejects(document("[[0,100000,81]]",",\"title\":\"\\ud800\""),MelodyError::Utf8);
    rejects(document("[[0,100000,81]]",",\"title\":\""+std::string("\xc0\x80",2)+"\""),MelodyError::Utf8);
    rejects(document("[[0,100000,81]]",",\"metadata\":{\"x\":"+std::string(20,'[')+"0"+std::string(20,']')+"}"),MelodyError::Depth);
    auto audit=document("[[0,100000,81]]",",\"title\":\"\\u7687\\u540e\\ud83c\\udfb5\",\"metadata\":{\"transpose_semitones_applied\":5,\"x\":[null,true,false,-1.25e+3,{\"s\":\"ok\"}]}");
    assert(load_melody(audit.data(),audit.size(),loaded));
    assert(loaded.notes[0].pitch==81 && loaded.notes[0].off==100000 && loaded.title_bytes==10);
    std::string many="[";
    for (unsigned i=0;i<4096;++i) {
        if (i) many+=",";
        many+="["+std::to_string(i*40001)+","+std::to_string(i*40001+1)+",81]";
    }
    // The independent byte limit may bind before 4096 JSON triples. Compact
    // 4096-event capacity is exercised separately via SongView.
    auto large=document(many+"]");
    if (large.size()>MELODY_MAX_BYTES) rejects(large,MelodyError::Size);
    assert(sizeof(LoadedSong)<50000);
    // Event capacity and very late polling are independent of JSON byte capacity.
    loaded.count=MELODY_MAX_NOTES; loaded.countdown_us=0;
    for (size_t i=0;i<loaded.count;++i) loaded.notes[i]={uint32_t(i*40001),uint32_t(i*40001+1),81};
    loaded.duration_us=loaded.notes[loaded.count-1].off+100;
    assert(p.start(loaded.view(),0));
    assert(!neutral(p.update(loaded.notes[4095].on)));
    assert(neutral(p.update(loaded.notes[4095].off)) && p.active());
    assert(neutral(p.update(loaded.duration_us)) && !p.active());
    auto title=document("[[0,100000,81]]",",\"title\":\""+std::string(80,'a')+"\"");
    assert(load_melody(title.data(),title.size(),loaded));
    auto escaped_key=replace(valid,"schema_version","schema_\\u0076ersion");
    assert(validate_melody(escaped_key.data(),escaped_key.size()));

    // All truncated prefixes and deterministic corruptions must reject safely
    // or produce a valid bounded song, never partially overwrite on failure.
    for (size_t n=0;n<valid.size();++n) {
        auto before=loaded.count; auto r=load_melody(valid.data(),n,loaded);
        assert(!r && loaded.count==before);
    }
    uint32_t seed=7;
    for (unsigned i=0;i<2000;++i) {
        auto text=valid; seed=seed*1664525u+1013904223u; size_t at=seed%text.size();
        seed=seed*1664525u+1013904223u; text[at]=char(seed>>24);
        auto r=load_melody(text.data(),text.size(),loaded);
        if (r) assert(loaded.count>0 && loaded.count<=MELODY_MAX_NOTES);
    }
    assert(!load_melody(reinterpret_cast<const char*>(&loaded),100,loaded));
    std::cout<<"PASS: fixture equality, deadline edges, 64-bit clock, bounded JSON and failure preservation\n";
}
