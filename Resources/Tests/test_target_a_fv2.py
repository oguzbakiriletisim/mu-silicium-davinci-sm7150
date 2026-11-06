"""Execute actual DXE FV2 matching, preventing a redundant huge FV extraction."""
import subprocess,tempfile,unittest
from pathlib import Path
from test_target_a_prepi_memory import ROOT,function
class Fv2Matching(unittest.TestCase):
 def test_actual_dispatcher_requires_both_parent_and_file_guid(self):
  source=(ROOT/'Mu_Basecore/MdeModulePkg/Core/Dxe/Dispatcher/Dispatcher.c').read_text()
  code=r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#define IN
#define CONST const
#define VOID void
#define EFIAPI
#define TRUE 1
#define FALSE 0
#define EFI_HOB_TYPE_FV2 9
#define GET_NEXT_HOB(h) ((void *)((char *)(h).Raw+sizeof(FV2)))
typedef int BOOLEAN;typedef struct{uint8_t b[16];} EFI_GUID;
typedef struct {EFI_GUID FvName,FileName;} FV2;
typedef union {void *Raw;FV2 *FirmwareVolume2;} EFI_PEI_HOB_POINTERS;
static FV2 Hob;static char Begin;static int First;
static void *GetHobList(void){First=1;return &Begin;}
static void *GetNextHob(int t,void *p){(void)t;(void)p;if(First){First=0;return &Hob;}return NULL;}
static int CompareGuid(const EFI_GUID*a,const EFI_GUID*b){return !memcmp(a,b,sizeof *a);}
'''+function(source,'FvFoundInHobFv2')+r'''
int main(void){EFI_GUID Parent={{1}},File={{2}},Other={{3}};
Hob.FvName=Parent;Hob.FileName=File;
assert(FvFoundInHobFv2(&Parent,&File));
assert(!FvFoundInHobFv2(&Other,&File));assert(!FvFoundInHobFv2(&Parent,&Other));
memset(&Hob.FvName,0xA5,sizeof Hob.FvName);memset(&Parent,0,sizeof Parent);
assert(!FvFoundInHobFv2(&Parent,&File));return 0;}
'''
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'t.c').write_text(code);subprocess.run(['cc','-Wall','-Wextra','-Werror',str(p/'t.c'),'-o',str(p/'t')],check=True);subprocess.run([str(p/'t')],check=True,timeout=10)
