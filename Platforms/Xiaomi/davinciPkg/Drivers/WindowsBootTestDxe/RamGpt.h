// SPDX-License-Identifier: BSD-2-Clause-Patent
// Validate our build-generated RAM-only disk. No phone GPT or MMIO/DMA.
#ifndef WBT_RAM_GPT_H
#define WBT_RAM_GPT_H
STATIC UINT32 WbtCrc(CONST UINT8 *P,UINTN N) {
 UINT32 C=0xffffffffU;UINTN I,B;
 for(I=0;I<N;++I) {C^=P[I];for(B=0;B<8;++B) {C=(C>>1)^(0xedb88320U&(0U-(C&1)));}}
 return ~C;
}
STATIC BOOLEAN WbtGptHeaderValid(CONST UINT8 *P,UINT64 Here,UINT64 Backup,UINT64 Table,UINT64 Total) {
 UINT8 Header[92];UINTN I;UINT32 Expected;
 if(WbtLe64(P)!=0x5452415020494645ULL || WbtLe32(P+8)!=0x10000 || WbtLe32(P+12)!=92 ||
    WbtLe32(P+20)!=0 || WbtLe64(P+24)!=Here || WbtLe64(P+32)!=Backup ||
    WbtLe64(P+40)!=34 || WbtLe64(P+48)!=Total-34 || WbtLe64(P+72)!=Table ||
    WbtLe32(P+80)!=128 || WbtLe32(P+84)!=128) {return FALSE;}
 for(I=0;I<92;++I) {Header[I]=P[I];}
 Expected=WbtLe32(P+16);for(I=16;I<20;++I) {Header[I]=0;}
 return WbtCrc(Header,92)==Expected;
}
STATIC BOOLEAN WbtGptValid(CONST UINT8 *P,UINTN N,CONST UINT8 **Fat,UINTN *FatBytes) {
 CONST UINT8 Esp[16]={0x28,0x73,0x2a,0xc1,0x1f,0xf8,0xd2,0x11,0xba,0x4b,0x00,0xa0,0xc9,0x3e,0xc9,0x3b};
 UINTN I,Total;CONST UINT8 *Backup,*Entries;
 // Deliberately scoped to the supplied 36 MiB FAT in a 40 MiB RAM disk.
 if(!P || !Fat || !FatBytes || N!=40U*1024U*1024U) {return FALSE;}
 Total=N/512;Backup=P+N-512;Entries=P+1024;
 if(P[510]!=0x55 || P[511]!=0xaa || P[450]!=0xee || WbtLe32(P+454)!=1 || WbtLe32(P+458)!=Total-1 ||
    !WbtGptHeaderValid(P+512,1,Total-1,2,Total) || !WbtGptHeaderValid(Backup,Total-1,1,Total-33,Total)) {return FALSE;}
 for(I=0;I<16;++I) {if(Entries[I]!=Esp[I] || P[512+56+I]!=Backup[56+I]) {return FALSE;}}
 for(I=0;I<16384;++I) {if(Entries[I]!=P[(Total-33)*512+I]) {return FALSE;}}
 if(WbtCrc(Entries,16384)!=WbtLe32(P+512+88) || WbtLe32(P+512+88)!=WbtLe32(Backup+88) ||
    WbtLe64(Entries+32)!=2048 || WbtLe64(Entries+40)!=2048+73728-1 || WbtLe64(Entries+48)!=0) {return FALSE;}
 for(I=128;I<16384;++I) {if(Entries[I]) {return FALSE;}}
 *Fat=P+2048*512;*FatBytes=36U*1024U*1024U;
 return WbtFatValid(*Fat,*FatBytes);
}
#endif
