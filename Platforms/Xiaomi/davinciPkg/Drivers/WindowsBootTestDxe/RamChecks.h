// SPDX-License-Identifier: BSD-2-Clause-Patent
// Pure bounds/format checks; no firmware services, MMIO or DMA.
#ifndef WBT_RAM_CHECKS_H
#define WBT_RAM_CHECKS_H
STATIC UINT32 WbtLe32(CONST UINT8 *P) {return (UINT32)P[0]|((UINT32)P[1]<<8)|((UINT32)P[2]<<16)|((UINT32)P[3]<<24);}
STATIC UINT64 WbtLe64(CONST UINT8 *P) {return WbtLe32(P)|((UINT64)WbtLe32(P+4)<<32);}
STATIC UINT32 WbtLe24(CONST UINT8 *P) {return P[0]|((UINT32)P[1]<<8)|((UINT32)P[2]<<16);}
STATIC BOOLEAN WbtFatValid(CONST UINT8 *P,UINTN N) {
 UINT32 Total,Fat,Data,Clusters;
 if(!P || N<512 || N>40U*1024U*1024U || (N%512) || P[510]!=0x55 || P[511]!=0xaa ||
    P[11]!=0 || P[12]!=2 || P[13]!=1 || P[14]!=32 || P[15]!=0 || P[16]!=2 ||
    P[17] || P[18] || P[19] || P[20] || P[22] || P[23]) {return FALSE;}
 Total=WbtLe32(P+32);Fat=WbtLe32(P+36);
 if(Total!=N/512 || Fat==0 || Fat>(Total-32)/2) {return FALSE;}
 Data=32+2*Fat;Clusters=Total-Data;
 return Clusters>=65525 && Clusters<0x0ffffff5 && ((UINT64)Clusters+2)*4<=(UINT64)Fat*512 && WbtLe32(P+44)==2;
}
STATIC BOOLEAN WbtReadRange(UINT64 Lba,UINTN Bytes,UINTN ImageBytes) {
 return (Bytes%512)==0 && Lba<=(UINT64)ImageBytes/512 && Bytes<=(UINT64)ImageBytes-Lba*512;
}
STATIC BOOLEAN WbtArmPe(CONST UINT8 *P,UINTN N) {
 UINT32 Offset;
 if(!P || N<64 || P[0]!='M' || P[1]!='Z') {return FALSE;}
 Offset=WbtLe32(P+60);
 return Offset<=N-26 && WbtLe32(P+Offset)==0x4550 && P[Offset+4]==0x64 && P[Offset+5]==0xaa && P[Offset+24]==0x0b && P[Offset+25]==2;
}
STATIC BOOLEAN WbtMapValid(CONST UINT8 *P,UINTN N,UINTN Stride) {
 UINTN I,J;UINT64 Start,Pages,End,Other,OtherPages;UINT32 Type;
 if(!P || Stride<40 || Stride>256 || !N || N%Stride || N/Stride>1024) {return FALSE;}
 for(I=0;I<N;I+=Stride) {
  Type=WbtLe32(P+I);Start=WbtLe64(P+I+8);Pages=WbtLe64(P+I+24);
  if((Start&4095) || !Pages || Pages>((~(UINT64)0-Start)/4096)) {return FALSE;}
  if((Type==5 || Type==6) && !(WbtLe64(P+I+32)&0x8000000000000000ULL)) {return FALSE;}
  End=Start+Pages*4096;
  for(J=0;J<I;J+=Stride) {
   Other=WbtLe64(P+J+8);OtherPages=WbtLe64(P+J+24);
   if(Start<Other+OtherPages*4096 && Other<End) {return FALSE;}
  }
 }
 return TRUE;
}
// Locate RAW without ReadSection's second 36MiB allocation. Parent FV is the
// already decompressed, trusted build FV; verify every length before traversal.
STATIC BOOLEAN WbtRawFromFv(CONST UINT8 *P,UINTN N,CONST UINT8 Guid[16],CONST UINT8 **Data,UINTN *Bytes) {
 UINTN F,End,Header,S,Sh,Len,I;UINT64 Volume,File;
 if(!P || N<56 || WbtLe32(P+40)!=0x4856465f) {return FALSE;}
 Volume=WbtLe64(P+32);Header=(UINTN)P[48]|((UINTN)P[49]<<8);
 if(Volume>N || Header<56 || Header>Volume || (Header&7)) {return FALSE;}
 for(F=Header;F+24<=Volume;) {
  File=WbtLe24(P+F+20);Header=24;
  if(File==0xffffff && P[F]==0xff) {break;}
  if(P[F+19]&1) {
   // PI EFI_FFS_FILE_HEADER2 requires Size[3]==0, unlike SECTION2's
   // 0xffffff marker. Match the actual GenFfs output and PI definition.
   if(File!=0 || Volume-F<32) {return FALSE;} File=WbtLe64(P+F+24);Header=32;
  }
  if(File<Header || File>Volume-F) {return FALSE;}
  for(I=0;I<16 && P[F+I]==Guid[I];++I) {}
  if(I==16 && P[F+18]==2) {
   End=F+(UINTN)File;
   for(S=F+Header;S+4<=End;) {
    Len=WbtLe24(P+S);Sh=4;
    if(Len==0xffffff) {if(End-S<8) {return FALSE;} Len=WbtLe32(P+S+4);Sh=8;}
    if(Len<Sh || Len>End-S) {return FALSE;}
    if(P[S+3]==0x19) {*Data=P+S+Sh;*Bytes=Len-Sh;return TRUE;}
    S=(S+Len+3)&~(UINTN)3;
   }
   return FALSE;
  }
  F=(F+(UINTN)File+7)&~(UINTN)7;
 }
 return FALSE;
}
#endif
