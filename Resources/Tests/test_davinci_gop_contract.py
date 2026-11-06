"""Execute actual SimpleFb QueryMode/SetMode source against host RAM."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]

class GopContract(unittest.TestCase):
 def test_actual_query_and_set_mode(self):
  source=(ROOT/'Silicon/Silicium/SiliciumPkg/Drivers/SimpleFbDxe/SimpleFbDxe.c').read_text()
  code=source[source.index('EFI_STATUS\nDisplayQueryMode'):source.index('EFI_STATUS\nDisplayBlt')]
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)
   (p/'c.c').write_text('''#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define IN
#define OUT
#define VOID void
#define EFI_SUCCESS 0
#define EFI_INVALID_PARAMETER 2
#define EFI_UNSUPPORTED 3
#define EFI_OUT_OF_RESOURCES 9
#define EFI_NOT_READY 6
#define EFI_ERROR(x) ((x)!=0)
#define EFI_D_ERROR 1
#define DEBUG(x) do{}while(0)
typedef uint32_t UINT32;typedef size_t UINTN;typedef int EFI_STATUS;
typedef struct {UINT32 Version,HorizontalResolution,VerticalResolution,PixelFormat,PixelInformation[4],PixelsPerScanLine;} EFI_GRAPHICS_OUTPUT_MODE_INFORMATION;
typedef struct {UINT32 MaxMode,Mode;EFI_GRAPHICS_OUTPUT_MODE_INFORMATION *Info;UINTN FrameBufferBase,FrameBufferSize;} Mode;
typedef struct {Mode *Mode;} EFI_GRAPHICS_OUTPUT_PROTOCOL;
static int allocs,failalloc;
static EFI_STATUS Allocate(int T,UINTN N,VOID **P){(void)T;allocs++;if(failalloc)return 9;*P=malloc(N);memset(*P,0xA5,N);return 0;}
static struct {EFI_STATUS(*AllocatePool)(int,UINTN,VOID**);} Bs={Allocate};
#define gBS (&Bs)
#define EfiBootServicesData 4
#define CopyMem memcpy
#define SetMem(P,N,V) memset(P,V,N)
static int flushed;static void WriteBackInvalidateDataCacheRange(void *P,UINTN N){assert(P&&N);flushed++;}
'''+code+'''\nint main(void){EFI_GRAPHICS_OUTPUT_MODE_INFORMATION info={.PixelInformation={1,2,3,4}},*out=NULL;unsigned char fb[16];memset(fb,0xA5,sizeof fb);Mode mode={1,0,&info,(UINTN)fb,sizeof fb};EFI_GRAPHICS_OUTPUT_PROTOCOL g={&mode};UINTN n=0;
assert(DisplayQueryMode(NULL,0,&n,&out)==2);assert(DisplayQueryMode(&g,0,NULL,&out)==2);assert(DisplayQueryMode(&g,0,&n,NULL)==2);assert(allocs==0);
assert(DisplayQueryMode(&g,1,&n,&out)==2);assert(out==NULL&&allocs==0);assert(DisplaySetMode(&g,1)==3);assert(DisplaySetMode(&g,0)==0);assert(fb[0]==0&&fb[15]==0&&flushed==1);
assert(DisplayQueryMode(&g,0,&n,&out)==0);assert(n==sizeof(info)&&memcmp(out,&info,n)==0);free(out);
failalloc=1;assert(DisplayQueryMode(&g,0,&n,&out)==9);return 0;}\n''')
   subprocess.run(['cc','-Wall','-Wextra','-Werror',str(p/'c.c'),'-o',str(p/'c')],check=True);subprocess.run([str(p/'c')],check=True)

