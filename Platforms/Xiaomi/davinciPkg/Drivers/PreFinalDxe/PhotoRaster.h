// SPDX-License-Identifier: BSD-2-Clause-Patent
// Bounded, allocation-free 5x12 font renderer, shared with host tests.
#ifndef DAVINCI_PHOTO_RASTER_H
#define DAVINCI_PHOTO_RASTER_H
STATIC BOOLEAN PhotoRasterValid (UINTN Width, UINTN Height, UINTN Bytes) {
  return Width == 1080 && Height == 2340 && Bytes >= 1080U*2340U*4U;
}
STATIC VOID PhotoGlyph (UINT32 *Pixels, UINTN Width, UINTN Height,
                       UINTN X, UINTN Y, UINT8 C, CONST UINTN *Font, UINT32 Color) {
  UINTN Dx, Dy, Sx, Sy; UINT32 Word;
  if (Pixels == NULL || Font == NULL || X > Width || Y > Height || Width-X < 15 || Height-Y < 36) { return; }
  if (C < 32 || C > 126) { C = '?'; }
  for (Dy=0; Dy<12; ++Dy) {
    Word=(UINT32)Font[(C-32)*2+Dy/6];
    for (Dx=0; Dx<5; ++Dx) {
      UINT32 V=(Word & (1U<<((Dy%6)*5+Dx))) ? Color : 0xff000000U;
      for (Sy=0; Sy<3; ++Sy) { for (Sx=0; Sx<3; ++Sx) { Pixels[(Y+Dy*3+Sy)*Width+X+Dx*3+Sx]=V; } }
    }
  }
}
#endif
