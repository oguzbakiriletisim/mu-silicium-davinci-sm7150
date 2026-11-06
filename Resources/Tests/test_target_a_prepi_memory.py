"""Execute actual old/new FfsProcessSection and real PrePi allocator on a 69 MiB arena.
Codec is mocked; section headers/sizes and downstream alignment branch are real.
No phone, MMIO, firmware binary or Microsoft payload is executed here.
"""
import re,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def function(text,name):
 p=re.search(r'^'+re.escape(name)+r' \(',text,re.M).start();start=max(text.rfind('\n\n',0,p)+2,text.rfind('*/',0,p)+2)
 a=text.index('{',p);depth=1;b=a+1
 while depth:
  depth+=(text[b]=='{')-(text[b]=='}');b+=1
 return text[start:b]
PREFIX=r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define STATIC static
#define EFIAPI
#define IN
#define OUT
#define VOID void
#define TRUE 1
#define FALSE 0
#define NULL_HOB NULL
#define DEBUG(x) ((void)0)
#define DEBUG_ERROR 0
#define ASSERT assert
#define EFI_SUCCESS 0
#define EFI_OUT_OF_RESOURCES 9
#define EFI_NOT_FOUND 14
#define EFI_UNSUPPORTED 3
#define EFI_VOLUME_CORRUPTED 10
#define EFI_ERROR(s) ((s)!=0)
#define EFI_PAGE_SIZE 4096U
#define EFI_PAGE_MASK 4095U
#define EFI_SIZE_TO_PAGES(n) (((n)+4095U)/4096U)
#define MAX_ADDRESS UINTPTR_MAX
#define EfiBootServicesData 4
#define EFI_SECTION_COMPRESSION 1
#define EFI_SECTION_GUID_DEFINED 2
#define EFI_STANDARD_COMPRESSION 1
#define SECTION_SIZE(p) ((p)->Size[0]|((p)->Size[1]<<8)|((p)->Size[2]<<16))
#define SECTION2_SIZE(p) (((EFI_COMMON_SECTION_HEADER2 *)(p))->ExtendedSize)
#define IS_SECTION2(p) (SECTION_SIZE(p)==0xffffff)
#define GET_OCCUPIED_SIZE(n,a) (((n)+(a)-1)&~((a)-1))
#define CopyMem memmove
#define ASSERT_EFI_ERROR(s) assert((s)==0)
typedef uint8_t UINT8;typedef uint16_t UINT16;typedef uint32_t UINT32;typedef uint64_t UINT64,EFI_PHYSICAL_ADDRESS;typedef size_t UINTN;typedef char CHAR8;typedef int BOOLEAN,EFI_STATUS,EFI_MEMORY_TYPE,EFI_SECTION_TYPE;
#pragma pack(push,1)
typedef struct {UINT8 Size[3],Type;} EFI_COMMON_SECTION_HEADER;
typedef struct {UINT8 Size[3],Type;UINT32 ExtendedSize;} EFI_COMMON_SECTION_HEADER2;
typedef struct {EFI_COMMON_SECTION_HEADER H;UINT32 UncompressedLength;UINT8 CompressionType;} EFI_COMPRESSION_SECTION;
typedef struct {EFI_COMMON_SECTION_HEADER2 H;UINT32 UncompressedLength;UINT8 CompressionType;} EFI_COMPRESSION_SECTION2;
#pragma pack(pop)
typedef EFI_STATUS (*FFS_CHECK_SECTION_HOOK)(EFI_COMMON_SECTION_HEADER *);
typedef struct {EFI_PHYSICAL_ADDRESS EfiFreeMemoryTop,EfiFreeMemoryBottom;} EFI_HOB_HANDOFF_INFO_TABLE;
typedef struct {char bytes[48];} EFI_HOB_MEMORY_ALLOCATION;
typedef union {void *Raw;EFI_HOB_HANDOFF_INFO_TABLE *HandoffInformationTable;} EFI_PEI_HOB_POINTERS;
static EFI_HOB_HANDOFF_INFO_TABLE Phi;
static void *GetHobList(void){return &Phi;}
static void BuildMemoryAllocationHob(EFI_PHYSICAL_ADDRESS a,size_t b,int c){(void)a;(void)b;(void)c;Phi.EfiFreeMemoryBottom+=48;}
static UINT8 *Decoded;static UINT32 DecodedBytes;
static EFI_STATUS ExtractGuidedSectionGetInfo(void *a,UINT32 *n,UINT32 *s,UINT16 *f){(void)a;*n=DecodedBytes;*s=65536;*f=1;return 0;}
static EFI_STATUS UefiDecompressGetInfo(void *a,UINT32 b,UINT32 *n,UINT32 *s){(void)a;(void)b;*n=DecodedBytes;*s=65536;return 0;}
static EFI_STATUS UefiDecompress(void*a,void*b,void*c){(void)a;(void)c;memcpy(b,Decoded,DecodedBytes);return 0;}
static EFI_STATUS ExtractGuidedSectionDecode(void*a,void**b,void*c,UINT32*d){(void)a;(void)c;*d=0;memcpy(*b,Decoded,DecodedBytes);return 0;}
'''
class PrePiMemory(unittest.TestCase):
 def test_actual_prepi_old_fails_new_fits_and_both_header_widths_align(self):
  alloc=(ROOT/'Common/Mu_Tiano_Plus/EmbeddedPkg/Library/PrePiMemoryAllocationLib/MemoryAllocationLib.c').read_text()
  for fixed in (False,True):
   path=('Platforms/Xiaomi/davinciPkg/Library/WindowsPrePiLib/FwVol.c' if fixed else 'Common/Mu_Tiano_Plus/EmbeddedPkg/Library/PrePiLib/FwVol.c')
   text=(ROOT/path).read_text();section=function(text,'FfsProcessSection')
   a=text.index('  if ((UINTN)FvImageInfo.FvStart % FvAlignment != 0) {');b=text.index('  //\n  // Inform HOB',a)
   align=text[a:b]
   code=PREFIX+function(alloc,'InternalAllocatePages')+'\n'+function(alloc,'AllocatePages')+'\n'+function(alloc,'AllocateAlignedPages')+'\n'+section+r'''
typedef void *EFI_PEI_FV_HANDLE;
typedef struct {void *FvStart;UINT64 FvSize;} INFO;
static int FfsGetVolumeInfo(void *p,INFO *i){i->FvStart=p;return 0;}
static int realign(void *p,size_t n){INFO FvImageInfo={p,n};UINT32 FvAlignment=8;void *FvBuffer;
'''+align+r'''
return 0;}
int main(void){
 void *Arena;assert(posix_memalign(&Arena,4096,0x4500000)==0);
 for(int large=0;large<2;large++){
  size_t fv=large?43057152:1024*1024,h=large?8:4;
  DecodedBytes=(UINT32)(fv+h);Decoded=calloc(1,DecodedBytes);assert(Decoded);
  EFI_COMMON_SECTION_HEADER2 *inner=(void*)Decoded;inner->Type=0x17;
  if(large){memset(inner->Size,255,3);inner->ExtendedSize=DecodedBytes;}
  else{inner->Size[0]=DecodedBytes;inner->Size[1]=DecodedBytes>>8;inner->Size[2]=DecodedBytes>>16;}
  Phi.EfiFreeMemoryBottom=(uintptr_t)Arena+4096;
  Phi.EfiFreeMemoryTop=(uintptr_t)Arena+0x4500000-0x40000;
  EFI_COMMON_SECTION_HEADER outer={{32,0,0},2};void *p=NULL;
  assert(FfsProcessSection(0x17,NULL,&outer,32,&p)==0);
  assert(memcmp(p,Decoded+h,fv)==0);
  int status=realign(p,fv);
  printf("fixed=%d large=%d offset_mod_8=%zu realign_status=%d remaining=%llu\n",FIXED,large,(uintptr_t)p%8,status,(unsigned long long)(Phi.EfiFreeMemoryTop-Phi.EfiFreeMemoryBottom));
  if(FIXED || !large){assert((uintptr_t)p%4096==0);assert(status==0);}
  else{assert((uintptr_t)p%8==4);assert(status==EFI_OUT_OF_RESOURCES);}
  free(Decoded);
 }
 free(Arena);return 0;}
'''
   with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp);(p/'test.c').write_text(code)
    subprocess.run(['cc','-std=c11','-D_POSIX_C_SOURCE=200112L',f'-DFIXED={int(fixed)}','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-but-set-variable',str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
