#include "melody.h"
#include "fingering.h"
#include <cstring>
#include <limits>
#include <initializer_list>

namespace {
class Parser {
public:
    Parser(const char* data, size_t size, LoadedSong* output, MelodyInfo* info=nullptr)
        : data_(data), size_(size), output_(output), info_(info) {}
    MelodyResult parse() {
        if (!data_ || size_ == 0 || size_ > MELODY_MAX_BYTES) {
            fail(MelodyError::Size); return result_;
        }
        if (!expect('{')) return result_;
        uint32_t fields = 0;
        ws();
        if (!take('}')) {
            do {
                char key[64];
                if (!string(key, sizeof key, 63) || !expect(':')) return result_;
                unsigned id = 0;
                while (id < 8 && std::strcmp(key, names_[id]) != 0) ++id;
                if (id == 8) { fail(MelodyError::UnknownField); return result_; }
                field_ = names_[id];
                if (fields & (1u << id)) { fail(MelodyError::DuplicateField); return result_; }
                fields |= 1u << id;
                uint32_t value = 0;
                char literal[64];
                switch (id) {
                case 0:
                    if (!string(literal, sizeof literal, 63)) return result_;
                    if (std::strcmp(literal, "pico-ocarina-melody") != 0) fail(MelodyError::Format);
                    break;
                case 1:
                    if (!integer(value)) return result_;
                    if (value != 1) fail(MelodyError::Version);
                    break;
                case 2:
                    if (!string(literal, sizeof literal, 63)) return result_;
                    if (std::strcmp(literal, MELODY_PROFILE) != 0) fail(MelodyError::Profile);
                    break;
                case 3:
                    if (!integer(countdown_)) return result_;
                    if (countdown_ > 10000000) fail(MelodyError::Range);
                    break;
                case 4:
                    if (!integer(duration_)) return result_;
                    if (duration_ == 0 || duration_ > MELODY_MAX_DURATION_US) fail(MelodyError::Range);
                    break;
                case 5: if (!notes()) return result_; break;
                case 6: if (!string(title_, sizeof title_, 80, &title_bytes_)) return result_; break;
                case 7: if (!object(1)) return result_; break;
                }
                if (result_.error != MelodyError::Ok) return result_;
            } while (take(','));
            if (!expect('}')) return result_;
        }
        if ((fields & 63) != 63) {
            for (unsigned id=0; id<6; ++id) if (!(fields & (1u << id))) { field_=names_[id]; break; }
            fail(MelodyError::MissingField); return result_;
        }
        if (last_off_ > duration_) { field_="notes"; note_=count_-1; fail(MelodyError::Timing); return result_; }
        ws();
        if (pos_ != size_) { fail(MelodyError::Syntax); return result_; }
        if (output_) {
            output_->count=count_; output_->duration_us=duration_; output_->countdown_us=countdown_;
            std::memcpy(output_->title, title_, sizeof title_); output_->title_bytes=title_bytes_;
        }
        if (info_) *info_={count_,duration_,countdown_};
        return result_;
    }
private:
    static constexpr const char* names_[8] = {
        "format","schema_version","fingering_profile","countdown_us","duration_us","notes","title","metadata"
    };
    const char* data_;
    size_t size_, pos_=0, count_=0, note_=size_t(-1);
    LoadedSong* output_;
    MelodyInfo* info_;
    MelodyResult result_;
    const char* field_="";
    uint32_t duration_=0, countdown_=0, last_off_=0;
    char title_[321]{};
    size_t title_bytes_=0;

    bool fail(MelodyError error) {
        if (result_.error == MelodyError::Ok) result_={error,pos_,note_,field_};
        return false;
    }
    void ws() { while (pos_<size_ && (data_[pos_]==' ' || data_[pos_]=='\n' || data_[pos_]=='\r' || data_[pos_]=='\t')) ++pos_; }
    bool take(char c) {
        ws();
        if (pos_<size_ && data_[pos_]==c) { ++pos_; return true; }
        return false;
    }
    bool expect(char c) { return take(c) || fail(MelodyError::Syntax); }
    bool digit() const { return pos_<size_ && data_[pos_]>='0' && data_[pos_]<='9'; }
    bool integer(uint32_t& value) {
        ws(); value=0;
        if (!digit()) return fail(MelodyError::Syntax);
        const bool zero=data_[pos_]=='0';
        do {
            unsigned d=unsigned(data_[pos_++]-'0');
            if (value>(std::numeric_limits<uint32_t>::max()-d)/10) return fail(MelodyError::Range);
            value=value*10+d;
            if (zero && digit()) return fail(MelodyError::Syntax);
        } while (digit());
        if (pos_<size_ && (data_[pos_]=='.' || data_[pos_]=='e' || data_[pos_]=='E')) return fail(MelodyError::Syntax);
        return true;
    }
    bool hex4(uint32_t& value) {
        value=0;
        for (unsigned i=0;i<4;++i) {
            if (pos_>=size_) return fail(MelodyError::Syntax);
            unsigned c=uint8_t(data_[pos_++]), d=16;
            if (c>='0' && c<='9') d=c-'0';
            if (c>='a' && c<='f') d=c-'a'+10;
            if (c>='A' && c<='F') d=c-'A'+10;
            if (d==16) return fail(MelodyError::Syntax);
            value=value*16+d;
        }
        return true;
    }
    bool string(char* output, size_t capacity, size_t max_chars, size_t* length=nullptr) {
        if (!expect('"')) return false;
        size_t used=0, chars=0;
        while (pos_<size_) {
            uint32_t cp=uint8_t(data_[pos_++]);
            if (cp=='"') {
                if (output) output[used]=0;
                if (length) *length=used;
                return true;
            }
            if (cp<32) return fail(MelodyError::Syntax);
            if (cp=='\\') {
                if (pos_>=size_) return fail(MelodyError::Syntax);
                char escaped=data_[pos_++];
                switch (escaped) {
                case '"': case '\\': case '/': cp=uint8_t(escaped); break;
                case 'b': cp=8; break;
                case 'f': cp=12; break;
                case 'n': cp=10; break;
                case 'r': cp=13; break;
                case 't': cp=9; break;
                case 'u': {
                    if (!hex4(cp)) return false;
                    if (cp>=0xd800 && cp<=0xdbff) {
                        if (pos_+2>size_ || data_[pos_]!='\\' || data_[pos_+1]!='u') return fail(MelodyError::Utf8);
                        pos_+=2; uint32_t low=0;
                        if (!hex4(low)) return false;
                        if (low<0xdc00 || low>0xdfff) return fail(MelodyError::Utf8);
                        cp=0x10000+((cp-0xd800)<<10)+(low-0xdc00);
                    } else if (cp>=0xdc00 && cp<=0xdfff) return fail(MelodyError::Utf8);
                    break;
                }
                default: return fail(MelodyError::Syntax);
                }
            } else if (cp>=128) {
                unsigned more=0; uint32_t minimum=0;
                if (cp>=0xc2 && cp<=0xdf) { more=1; minimum=0x80; cp&=31; }
                else if (cp>=0xe0 && cp<=0xef) { more=2; minimum=0x800; cp&=15; }
                else if (cp>=0xf0 && cp<=0xf4) { more=3; minimum=0x10000; cp&=7; }
                else return fail(MelodyError::Utf8);
                for (unsigned i=0;i<more;++i) {
                    if (pos_>=size_) return fail(MelodyError::Utf8);
                    uint8_t c=uint8_t(data_[pos_++]);
                    if ((c&0xc0)!=0x80) return fail(MelodyError::Utf8);
                    cp=(cp<<6)|(c&63);
                }
                if (cp<minimum || cp>0x10ffff || (cp>=0xd800 && cp<=0xdfff)) return fail(MelodyError::Utf8);
            }
            if (++chars>max_chars) return fail(MelodyError::Range);
            // Keys/literals must not hide suffixes behind embedded NUL.
            if (cp==0 && output && !length) return fail(MelodyError::Syntax);
            char encoded[4]; size_t bytes=0;
            if (cp<0x80) encoded[bytes++]=char(cp);
            else {
                if (cp>=0x10000) encoded[bytes++]=char(0xf0|(cp>>18));
                else if (cp>=0x800) encoded[bytes++]=char(0xe0|(cp>>12));
                else encoded[bytes++]=char(0xc0|(cp>>6));
                if (cp>=0x10000) encoded[bytes++]=char(0x80|((cp>>12)&63));
                if (cp>=0x800) encoded[bytes++]=char(0x80|((cp>>6)&63));
                encoded[bytes++]=char(0x80|(cp&63));
            }
            if (output) {
                if (used+bytes>=capacity) return fail(MelodyError::Range);
                std::memcpy(output+used,encoded,bytes);
            }
            used+=bytes;
        }
        return fail(MelodyError::Syntax);
    }
    bool notes() {
        if (!expect('[')) return false;
        if (take(']')) return fail(MelodyError::NoteCount);
        uint32_t previous_on=0;
        do {
            note_=count_;
            if (count_==MELODY_MAX_NOTES) return fail(MelodyError::NoteCount);
            uint32_t on=0, off=0, pitch=0;
            if (!expect('[') || !integer(on) || !expect(',') || !integer(off) ||
                !expect(',') || !integer(pitch) || !expect(']')) return false;
            if (on>=off || off>MELODY_MAX_DURATION_US) return fail(MelodyError::Timing);
            ControlState state;
            if (pitch>255 || !lookup_fingering(uint8_t(pitch),state)) return fail(MelodyError::Pitch);
            if (count_ && on<=previous_on) return fail(MelodyError::Order);
            if (count_ && (on<last_off_ || on-last_off_<MELODY_RELEASE_US)) return fail(MelodyError::ReleaseGap);
            if (output_) output_->notes[count_]={on,off,uint8_t(pitch)};
            previous_on=on; last_off_=off; ++count_;
        } while (take(','));
        note_=size_t(-1);
        return expect(']');
    }
    bool object(unsigned) {
        // Explicit bounded stack avoids recursive JSON calls on the Pico stack.
        enum State : uint8_t { KeyOrEnd, Key, ObjectValue, ObjectAfter,
                              ArrayValueOrEnd, ArrayValue, ArrayAfter };
        State stack[16]; size_t depth=1;
        if (!expect('{')) return false;
        stack[0]=KeyOrEnd;
        while (depth) {
            State& state=stack[depth-1];
            if (state==KeyOrEnd && take('}')) { --depth; continue; }
            if (state==KeyOrEnd || state==Key) {
                if (!string(nullptr,0,size_t(-1)) || !expect(':')) return false;
                state=ObjectValue; continue;
            }
            if (state==ObjectAfter || state==ArrayAfter) {
                bool object_after=state==ObjectAfter;
                if (take(',')) { state=object_after?Key:ArrayValue; continue; }
                if (!expect(object_after?'}':']')) return false;
                --depth; continue;
            }
            if (state==ArrayValueOrEnd && take(']')) { --depth; continue; }
            ws();
            if (pos_>=size_) return fail(MelodyError::Syntax);
            char next=data_[pos_];
            state=state==ObjectValue ? ObjectAfter : ArrayAfter;
            if (next=='{' || next=='[') {
                if (depth==16) return fail(MelodyError::Depth);
                ++pos_; stack[depth++]=next=='{'?KeyOrEnd:ArrayValueOrEnd;
            } else if (!scalar()) return false;
        }
        return true;
    }
    bool scalar() {
        ws();
        if (pos_>=size_) return fail(MelodyError::Syntax);
        char c=data_[pos_];
        if (c=='"') return string(nullptr,0,size_t(-1));
        for (const char* literal: {"true","false","null"}) {
            size_t n=std::strlen(literal);
            if (size_-pos_>=n && std::memcmp(data_+pos_,literal,n)==0) { pos_+=n; return true; }
        }
        // Metadata numbers need JSON lexical validation, never numeric coercion.
        if (c=='-') ++pos_;
        if (!digit()) return fail(MelodyError::Syntax);
        if (data_[pos_++]!='0') while (digit()) ++pos_;
        if (pos_<size_ && data_[pos_]=='.') {
            ++pos_; if (!digit()) return fail(MelodyError::Syntax);
            while (digit()) ++pos_;
        }
        if (pos_<size_ && (data_[pos_]=='e' || data_[pos_]=='E')) {
            ++pos_; if (pos_<size_ && (data_[pos_]=='+' || data_[pos_]=='-')) ++pos_;
            if (!digit()) return fail(MelodyError::Syntax);
            while (digit()) ++pos_;
        }
        return true;
    }
};
} // namespace

MelodyResult validate_melody(const char* bytes, size_t size, MelodyInfo* info) {
    return Parser(bytes,size,nullptr,info).parse();
}
MelodyResult load_melody(const char* bytes, size_t size, LoadedSong& destination) {
    // Overlapping input could change between the validation and materialization.
    uintptr_t begin=reinterpret_cast<uintptr_t>(bytes), out=reinterpret_cast<uintptr_t>(&destination);
    if ((begin<=out && out-begin<size) || (out<begin && begin-out<sizeof destination))
        return {MelodyError::Size,0,size_t(-1),""};
    auto result=validate_melody(bytes,size);
    if (!result) return result;
    return Parser(bytes,size,&destination).parse();
}
const char* melody_error_name(MelodyError error) {
    switch (error) {
    case MelodyError::Ok: return "ok";
    case MelodyError::Size: return "file_size";
    case MelodyError::Syntax: return "json_syntax";
    case MelodyError::Utf8: return "utf8";
    case MelodyError::Depth: return "metadata_depth";
    case MelodyError::DuplicateField: return "duplicate_field";
    case MelodyError::UnknownField: return "unknown_field";
    case MelodyError::MissingField: return "missing_field";
    case MelodyError::Format: return "format";
    case MelodyError::Version: return "schema_version";
    case MelodyError::Profile: return "fingering_profile";
    case MelodyError::Range: return "range";
    case MelodyError::NoteCount: return "note_count";
    case MelodyError::Pitch: return "missing_fingering";
    case MelodyError::Timing: return "note_time";
    case MelodyError::Order: return "note_order";
    case MelodyError::ReleaseGap: return "release_gap";
    }
    return "unknown";
}
