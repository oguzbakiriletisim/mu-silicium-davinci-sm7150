#!/usr/bin/env python3
"""Deterministic 36MiB FAT32 superfloppy, PC files only. No disk devices/mounts."""
import argparse,hashlib,importlib.util,json,math,struct,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('winprepare',ROOT/'Resources/Windows/davinci/prepare_windows.py');WIN=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(WIN)
SECTORS=73728;BPS=512;RESERVED=32

def shortname(name,used):
 up=name.upper();parts=up.rsplit('.',1);base=parts[0];ext=parts[1] if len(parts)>1 else ''
 valid=lambda x:all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in x)
 if 1<=len(base)<=8 and len(ext)<=3 and valid(base+ext):alias=base.ljust(8)+ext.ljust(3)
 else:
  stem=''.join(c for c in base if c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') or 'FILE'
  for n in range(1,10000):
   tail='~'+str(n);alias=(stem[:8-len(tail)]+tail).ljust(8)+''.join(c for c in ext if c.isalnum())[:3].ljust(3)
   if alias not in used:break
 if alias in used:raise ValueError('Duplicate DOS alias')
 used.add(alias);return alias.encode('ascii')
def lfn(name,alias):
 checksum=0
 for c in alias:checksum=(((checksum&1)<<7)+(checksum>>1)+c)&255
 units=list(struct.unpack('<'+'H'*(len(name.encode('utf-16-le'))//2),name.encode('utf-16-le')))+[0]
 units += [0xffff]*((-len(units))%13);rows=[]
 for k in reversed(range(len(units)//13)):
  b=bytearray(32);b[0]=k+1|(0x40 if k==len(units)//13-1 else 0);b[11]=0xf;b[13]=checksum
  for offset,value in zip([1,3,5,7,9,14,16,18,20,22,24,28,30],units[k*13:(k+1)*13]):struct.pack_into('<H',b,offset,value)
  rows.append(bytes(b))
 return b''.join(rows)
def create(files):
 fatsz=1
 while True:
  count=SECTORS-RESERVED-2*fatsz;needed=(4*(count+2)+511)//512
  if needed<=fatsz:break
  fatsz=needed
 assert 65525<=count<0xffffff5
 image=bytearray(SECTORS*BPS);fat=bytearray(fatsz*512);struct.pack_into('<II',fat,0,0x0ffffff8,0xffffffff)
 root={'children':{},'name':'','cluster':2};next_cluster=2
 for path,data in sorted(files.items()):
  parts=Path(path).parts
  if not parts or path.startswith('/') or any(x in ('.','..') for x in parts):raise ValueError('Unsafe FAT path')
  node=root
  for part in parts[:-1]:node=node['children'].setdefault(part,{'name':part,'children':{}})
  if parts[-1] in node['children']:raise ValueError('Duplicate path')
  node['children'][parts[-1]]={'name':parts[-1],'data':data}
 data_start=RESERVED+2*fatsz
 def allocate(n):
  nonlocal next_cluster
  first=next_cluster;next_cluster+=n
  if next_cluster>count+2:raise ValueError('Files exceed FAT32 capacity')
  for c in range(first,first+n):struct.pack_into('<I',fat,c*4,c+1 if c<first+n-1 else 0xfffffff)
  return first
 def entry(alias,attr,cluster,size=0):
  b=bytearray(32);b[:11]=alias;b[11]=attr
  for offset in (16,18,24):struct.pack_into('<H',b,offset,0x2821) # 2000-01-01, deterministic valid DOS date
  struct.pack_into('<H',b,20,cluster>>16);struct.pack_into('<H',b,26,cluster&65535);struct.pack_into('<I',b,28,size);return b
 def put(first,data):o=(data_start+first-2)*512;image[o:o+len(data)]=data
 def write(node,parent=0):
  children=node.get('children')
  if children is None:
   node['cluster']=allocate(max(1,(len(node['data'])+511)//512));put(node['cluster'],node['data']);return
  used=set()
  for name,n in sorted(children.items()):n['alias']=shortname(name,used);n['lfn']=lfn(name,n['alias'])
  size=(0 if node is root else 64)+sum(len(n['lfn'])+32 for n in children.values())+32
  node['cluster']=allocate((size+511)//512)
  rows=bytearray()
  if node is not root:rows+=entry(b'.          ',0x10,node['cluster'])+entry(b'..         ',0x10,parent)
  for name,n in sorted(children.items()):
   write(n,node['cluster'] if node is not root else 0)
   rows+=n['lfn']+entry(n['alias'],0x10 if 'children' in n else 0x20,n['cluster'],len(n.get('data',b'')))
  put(node['cluster'],rows)
 write(root);assert root['cluster']==2
 boot=bytearray(512);boot[:3]=b'\xeb\x58\x90';boot[3:11]=b'DAVINCI '
 struct.pack_into('<HBHBHHBHHHII',boot,11,512,1,32,2,0,0,0xf8,0,63,255,0,SECTORS)
 struct.pack_into('<IHHIHH',boot,36,fatsz,0,0,2,1,6);boot[64]=0x80;boot[66]=0x29
 struct.pack_into('<I',boot,67,0x44415649);boot[71:82]=b'DAVINCI EFI';boot[82:90]=b'FAT32   ';boot[510:512]=b'\x55\xaa'
 fs=bytearray(512);struct.pack_into('<I',fs,0,0x41615252);struct.pack_into('<III',fs,484,0x61417272,count-(next_cluster-2),next_cluster);struct.pack_into('<I',fs,508,0xaa550000)
 image[:512]=boot;image[512:1024]=fs;image[6*512:7*512]=boot;image[7*512:8*512]=fs
 for i in range(2):o=(RESERVED+i*fatsz)*512;image[o:o+len(fat)]=fat
 return image

def prepare(staging,bcd=None):
 staging=staging.resolve(strict=True);files={}
 p=WIN.contained_file(staging,'Windows/Boot/EFI/bootmgfw.efi');WIN.arm64_pe(p);data=p.read_bytes()
 files['EFI/Microsoft/Boot/bootmgfw.efi']=data;files['EFI/Boot/bootaa64.efi']=data
 for sub,target in [('Windows/Boot/Fonts','EFI/Microsoft/Boot/Fonts'),('Windows/Boot/EFI/en-US','EFI/Microsoft/Boot/en-US'),('Windows/Boot/Resources','EFI/Microsoft/Boot/Resources')]:
  d=staging/sub
  if d.is_dir():
   for p in sorted(d.rglob('*')):
    if p.is_file():
     # A Latin/en-US Target-A candidate, not the entire multilingual boot-font
     # set. Copying every CJK font would exceed the fixed 3MiB compressed FD.
     if sub=='Windows/Boot/Fonts' and p.name.lower() not in {'wgl4_boot.ttf','segoe_slboot.ttf','segoen_slboot.ttf','segmono_boot.ttf'}:continue
     p=WIN.contained_file(staging,str(p.relative_to(staging)));files[target+'/'+str(p.relative_to(d)).replace('\\','/')]=p.read_bytes()
 if bcd:WIN.hive_header(bcd);files['EFI/Microsoft/Boot/BCD']=bcd.read_bytes()
 return files
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--staging',type=Path);p.add_argument('--bcd',type=Path);p.add_argument('--fixture',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.fixture==bool(a.staging):p.error('Choose exactly one of --fixture or --staging')
 if a.output.exists():p.error('Output must be new; no overwrite')
 files={'README.TXT':b'HOST FIXTURE ONLY - NO MICROSOFT EFI FILES\r\n'} if a.fixture else prepare(a.staging,a.bcd)
 image=create(files);a.output.write_bytes(image)
 print(json.dumps({'image_bytes':len(image),'sha256':hashlib.sha256(image).hexdigest(),'fat32':True,'microsoft_payload_present':not a.fixture,'signature_verified':False,'physical_boot_verified':False,'files':{k:hashlib.sha256(v).hexdigest() for k,v in files.items()}},indent=2))
