from pathlib import Path
import json,struct,csv,argparse
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Generate the verified Queens Road East demonstration song.')
parser.add_argument('--variant',choices=['full','first'],default='full')
parser.add_argument('--source',type=Path,default=ROOT/'examples/queens_road_east/source_voice.json')
parser.add_argument('--output-dir',type=Path)
args=parser.parse_args()
OUT=args.output_dir or ROOT/'out/generated'/args.variant
OUT.mkdir(parents=True,exist_ok=True)
source=json.loads(args.source.read_text(encoding='utf-8'));raw=source['notes']
TEMPO=source['tempo_us'];PPQ=source['tpq'];start=44*PPQ
if args.variant=='first':raw=[n for n in raw if 44*PPQ<=n['t']<140*PPQ];end_tick=140*PPQ
else:end_tick=492*PPQ
# Five simultaneous octave doubles occur in source bar91. A single ocarina
# takes the higher voice there; all other notes are unchanged apart from +5.
groups={}
for n in raw:groups.setdefault(n['t'],[]).append(n)
notes=[max(v,key=lambda n:n['n']) for _,v in sorted(groups.items())]
rows=[]
for i,n in enumerate(notes):
 onset=round(Fraction((n['t']-start)*TEMPO,PPQ))
 off=round(Fraction((n['end']-start)*TEMPO,PPQ))
 nxt=round(Fraction(((notes[i+1]['t'] if i+1<len(notes) else end_tick)-start)*TEMPO,PPQ))
 off=min(off,nxt-40000);assert off>onset
 rows.append((onset,off,n['n']+5,n['n']))
assert len(rows)==(572 if args.variant=='full' else 132)
assert min(r[2] for r in rows)>=71 and max(r[2] for r in rows)<=89
for bar,expected in [(27,[77,74,74,72,74]),(51,[89,86,86,84,86]),(59,[89,86,86,84,86])]:
 a=[r[2] for r,n in zip(rows,notes) if (bar-1)*4*PPQ<=n['t']<bar*4*PPQ]
 if a:assert a==expected,(bar,a)
TOTAL=round(Fraction((end_tick-start)*TEMPO,PPQ))
text='#pragma once\n#include "melody.h"\n'
text+=f'constexpr uint32_t SONG_DURATION_US={TOTAL};\nconstexpr bool SONG_FULL={"true" if args.variant=="full" else "false"};\nconstexpr SongNote SONG[]={{\n'
text+=''.join(f' {{{on},{off},{p}}},\n' for on,off,p,_ in rows)+'};\nconstexpr unsigned SONG_COUNT=sizeof(SONG)/sizeof(SONG[0]);\n'
(OUT/'song.h').write_text(text)
with (OUT/f'song_{args.variant}_notes.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['onset_us','note_off_us','playback_MIDI_pitch','source_MIDI_pitch','original_bar'])
 for row,n in zip(rows,notes):w.writerow(list(row)+[n['t']//(PPQ*4)+1])
def vl(n):
 out=[n&127];n>>=7
 while n:out.insert(0,(n&127)|128);n>>=7
 return bytes(out)
def meta(ty,b):return bytes([255,ty])+vl(len(b))+b
def midi(name,shift):
 ev=[(0,0,meta(3,f'Queens Road East {args.variant} {"F playback" if shift else "C reference"}'.encode())),(0,1,b'\xff\x51\x03'+TEMPO.to_bytes(3,'big')),(0,2,b'\xff\x58\x04\x04\x02\x18\x08'),(0,3,bytes([0xc0,79]))]
 for (on,off,p,src),n in zip(rows,notes):
  if shift==0:off=round(Fraction((n['end']-start)*TEMPO,PPQ))
  ev.append((round(Fraction(on*960,TEMPO)),5,bytes([0x90,src+shift,90])))
  ev.append((round(Fraction(off*960,TEMPO)),4,bytes([0x80,src+shift,0])))
 ev.append((round(Fraction((end_tick-start)*960,PPQ)),9,b'\xff\x2f\x00'));ev.sort();data=b'';prev=0
 for t,_,b in ev:data+=vl(t-prev)+b;prev=t
 (OUT/name).write_bytes(b'MThd'+struct.pack('>IHHH',6,0,1,960)+b'MTrk'+struct.pack('>I',len(data))+data)
midi(f'preview_{args.variant}_F_v1_1.mid',5);midi(f'reference_{args.variant}_original_C_v1_1.mid',0)
print(args.variant,len(notes),'notes;',len(raw)-len(notes),'lower octave doubles omitted; duration',TOTAL/1e6,'range',min(r[2] for r in rows),max(r[2] for r in rows))

# A built-in demonstration remains available; it uses the same runtime parser.
config=(ROOT/f'examples/queens_road_east/melody_{args.variant}_v1_proposed.json').read_bytes()
(OUT/'fallback_melody.h').write_text('#pragma once\nconstexpr unsigned char FALLBACK_MELODY[]={'+','.join(str(b) for b in config)+'};\n')
