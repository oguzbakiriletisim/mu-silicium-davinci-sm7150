"""Exercise actual observation wrappers: no fabricated success or address redirect."""
import subprocess,tempfile,unittest
from pathlib import Path
from test_target_a_prepi_memory import ROOT
def function(text,name):
 p=text.index(name+"(");start=text.rfind("\n",0,p)+1;a=text.index("{",p);b=a+1;depth=1
 while depth:
  depth+=(text[b]=="{")-(text[b]=="}");b+=1
 return text[start:b]
class PageObserver(unittest.TestCase):
 def test_original_api_arguments_status_and_recursion_guard_preserved(self):
  text=(ROOT/'Platforms/Xiaomi/davinciPkg/Drivers/WindowsBootTestDxe/HandoffTrace.h').read_text()
  code=r'''
#include <stdint.h>
#include <stddef.h>
#include <assert.h>
#define STATIC static
#define EFIAPI
#define DEBUG(x) ((void)0)
#define DEBUG_ERROR 0
#define WBT_TRACE(x) DEBUG(x)
#define AllocateAddress 2
#define RETURN_ADDRESS(n) FixtureCaller
#define EFI_ERROR(s) (((s)>>63)!=0)
typedef uint64_t UINT64,EFI_STATUS,EFI_PHYSICAL_ADDRESS;
typedef uint32_t UINT32;
typedef uintptr_t UINTN;
typedef int BOOLEAN,EFI_ALLOCATE_TYPE,EFI_MEMORY_TYPE;
#define TRUE 1
#define FALSE 0
static UINTN FixtureCaller;
typedef EFI_STATUS (*EFI_ALLOCATE_PAGES)(EFI_ALLOCATE_TYPE,EFI_MEMORY_TYPE,UINTN,EFI_PHYSICAL_ADDRESS*);
typedef EFI_STATUS (*EFI_FREE_PAGES)(EFI_PHYSICAL_ADDRESS,UINTN);
static EFI_ALLOCATE_PAGES mRealAllocatePages;static EFI_FREE_PAGES mRealFreePages;
static BOOLEAN mTraceBusy;static UINTN mTracePhase=2,mPageCalls,mFreeCalls,mChildApiCalls;
static UINT64 mTraceChildBase=0x90000000,mTraceChildSize=0x10000;
static int Calls;static EFI_ALLOCATE_TYPE SeenType;static EFI_MEMORY_TYPE SeenKind;
static UINTN SeenPages;static EFI_PHYSICAL_ADDRESS SeenAddr,*SeenPointer;
static EFI_STATUS Result;
static EFI_STATUS Original(EFI_ALLOCATE_TYPE t,EFI_MEMORY_TYPE k,UINTN n,EFI_PHYSICAL_ADDRESS *p){
 Calls++;SeenType=t;SeenKind=k;SeenPages=n;SeenPointer=p;SeenAddr=p?*p:0;
 if(p && !EFI_ERROR(Result))*p=0x97700000;
 return Result;}
static EFI_STATUS OriginalFree(EFI_PHYSICAL_ADDRESS a,UINTN n){Calls++;SeenAddr=a;SeenPages=n;return Result;}
'''+function(text,'CallerIsChild')+'\n'+function(text,'TraceAllocatePages')+'\n'+function(text,'TraceFreePages')+r'''
int main(void){
 mRealAllocatePages=Original;mRealFreePages=OriginalFree;FixtureCaller=0x90000100;
 EFI_PHYSICAL_ADDRESS a=0x102000;Result=0x800000000000000eULL;
 assert(TraceAllocatePages(2,2,1,&a)==Result);
 assert(Calls==1&&SeenType==2&&SeenKind==2&&SeenPages==1&&SeenAddr==0x102000&&SeenPointer==&a&&a==0x102000);
 assert(mChildApiCalls==1&&mPageCalls==1&&!mTraceBusy);
 Result=0;a=0;assert(TraceAllocatePages(0,4,300,&a)==0&&a==0x97700000);
 assert(Calls==2&&SeenType==0&&SeenKind==4&&SeenPages==300&&mChildApiCalls==2);
 FixtureCaller=0x90010000;Result=0x8000000000000002ULL;
 assert(TraceAllocatePages(2,4,1,NULL)==Result&&SeenPointer==NULL&&mChildApiCalls==2);
 assert(TraceFreePages(0x102000,1)==Result&&SeenAddr==0x102000&&SeenPages==1&&mFreeCalls==1);
 mTraceBusy=TRUE;UINTN before=mPageCalls;
 assert(TraceAllocatePages(1,4,17,&a)==Result&&mPageCalls==before&&SeenPages==17);
 assert(mTraceBusy==TRUE);return 0;}
'''
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'t.c').write_text(code)
   subprocess.run(['cc','-Wall','-Wextra','-Werror','-Wno-unused-but-set-variable','-Wno-unused-variable',str(p/'t.c'),'-o',str(p/'t')],check=True)
   subprocess.run([str(p/'t')],check=True,timeout=10)
if __name__=='__main__':unittest.main()
