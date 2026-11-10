from pathlib import Path
import json,struct,argparse
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Check a generated demo MIDI against the source voice track.')
parser.add_argument('--variant',choices=['full','first'],default='full')
parser.add_argument('--output-dir',type=Path)
args=parser.parse_args()
OUT=args.output_dir or ROOT/'out/generated'/args.variant

def read(path,only_track=None):
 b=path.read_bytes();assert b[:4]==b'MThd';ppq=int.from_bytes(b[12:14],'big');pos=14;notes=[];tempo=None;track_index=-1
 def vl(d,p):
  n=0
  while True:
   x=d[p];p+=1;n=(n<<7)|(x&127)
   if not x&128:return n,p
 while pos<len(b):
  track_index+=1
  assert b[pos:pos+4]==b'MTrk';ln=int.from_bytes(b[pos+4:pos+8],'big');d=b[pos+8:pos+8+ln];pos+=8+ln;i=t=0;run=None;active={}
  while i<len(d):
   dt,i=vl(d,i);t+=dt;s=d[i]
   if s<128:s=run
   else:i+=1
   if s==255:
    ty=d[i];i+=1;n,i=vl(d,i)
    if ty==81:tempo=int.from_bytes(d[i:i+n],'big')
    i+=n;continue
   if s in [240,247]:n,i=vl(d,i);i+=n;continue
   run=s;ty=s>>4;ch=s&15;n=1 if ty in [12,13] else 2;v=d[i:i+n];i+=n
   if only_track is not None and track_index!=only_track:continue
   if ty==9 and v[1]:assert (ch,v[0]) not in active;active[(ch,v[0])]=t
   elif ty==8 or (ty==9 and not v[1]):
    on=active.pop((ch,v[0]));notes.append((on,t,v[0]))
  assert not active
 return sorted(notes),ppq,tempo
source=json.loads((ROOT/'examples/queens_road_east/source_voice.json').read_text(encoding='utf-8'));g={}
raw,raw_ppq,raw_tempo=read(ROOT/'examples/queens_road_east/source.mid',only_track=2)
assert raw_ppq==source['tpq'] and raw_tempo==source['tempo_us']
assert raw==sorted((n['t'],n['end'],n['n']) for n in source['notes'])
print('Original attached MIDI voice track matches all 577 source JSON events')
for n in source['notes']:g.setdefault(n['t'],[]).append(n)
mono=[max(v,key=lambda n:n['n']) for _,v in sorted(g.items())]
for variant in [args.variant]:
 selected=mono if variant=='full' else [n for n in mono if n['t']<140*96]
 ref,ppq,tempo=read(OUT/f'reference_{variant}_original_C_v1_1.mid')
 play,_,_=read(OUT/f'preview_{variant}_F_v1_1.mid')
 assert ppq==960 and tempo==508475 and len(ref)==len(play)==len(selected)
 for n,a,p in zip(selected,ref,play):
  assert a==((n['t']-44*96)*10,(n['end']-44*96)*10,n['n'])
  assert p[0]==a[0] and p[2]==a[2]+5 and p[1]<=a[1]
 print('Verified',variant,len(play),'notes: exact source pitch/onset/duration in C reference; uniform +5 and same onsets in F playback')
first,_,_=read(OUT/f'preview_{args.variant}_F_v1_1.mid');assert [x[2] for x in first if x[0] in [57600,58080,58560,59040,59520]]==[77,74,74,72,74]
print('First ending specifically verified in LOW octave: F5 D5 D5 C5 D5')
