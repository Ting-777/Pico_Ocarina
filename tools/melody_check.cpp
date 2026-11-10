#include "melody.h"
#include "fingering.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
static LoadedSong song;
int main(int argc,char** argv) {
    if (argc<2 || argc>3) return 2;
    std::ifstream file(argv[1],std::ios::binary);
    if (!file) { std::cerr<<"Cannot open file\n"; return 2; }
    // Limit allocation even for hostile input on the desktop.
    std::string bytes(MELODY_MAX_BYTES+1,'\0');
    file.read(bytes.data(),std::streamsize(bytes.size())); bytes.resize(size_t(file.gcount()));
    auto r=load_melody(bytes.data(),bytes.size(),song);
    if (!r) {
        std::cerr<<melody_error_name(r.error)<<" field="<<r.field<<" offset="<<r.offset<<" note="<<r.note_index<<"\n";
        return 1;
    }
    std::cout<<song.count<<","<<song.duration_us<<","<<song.countdown_us<<"\n";
    if (argc==3 && std::string(argv[2])=="--events") for (size_t i=0;i<song.count;++i) {
        auto n=song.notes[i]; auto s=fingering(n.pitch);
        std::cout<<n.on<<","<<n.off<<","<<unsigned(n.pitch)<<","<<unsigned(s.right)<<","
                 <<unsigned(s.shared)<<","<<unsigned(s.left)<<","<<s.lx<<","<<s.ly<<","<<s.rx<<","<<s.ry<<"\n";
    }
}
