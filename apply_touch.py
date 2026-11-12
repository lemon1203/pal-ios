#!/usr/bin/env python3
"""
给 SDLPAL 换成现代触屏操作：左下虚拟摇杆 + 右下 4 个圆钮。

- 摇杆：固定左下角，推杆决定 4 个方向（游戏本身只有 4 向）
- 按钮：A=确认/调查  B=菜单/取消  C=战斗自动 / 场景用道具  D=战斗防御
- 绘制：运行时用 SDL 生成圆形纹理，不依赖 BMP 覆盖层

用法: python3 apply_touch.py <sdlpal 源码根目录>
"""

import io
import os
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else '.'

MARKER_INPUT = '/* ===== joystick touch (patched) ===== */'
MARKER_VIDEO = '/* ===== joystick overlay (patched) ===== */'

INPUT_CODE = r'''
/* ===== joystick touch (patched) ===== */
#define JS_BTN_COUNT 4

BOOL  g_fStickActive   = FALSE;
double g_dStickDX      = 0.0;
double g_dStickDY      = 0.0;
int   g_iPressedButton = -1;

static BOOL   g_fJSHooked = FALSE;
static double g_dJSCX = 0.0, g_dJSCY = 0.0, g_dJSR = 0.0;
static double g_dJSBtn[4][3];   // x, y, r

//
// 计算布局：摇杆在左下，四个按钮在右下
//   btn[0]=A(确认/调查) btn[1]=B(菜单/取消) btn[2]=C(自动/道具) btn[3]=D(防御)
//
VOID
PAL_GetTouchLayout(
   int     iWidth,
   int     iHeight,
   double *pdStickCX,
   double *pdStickCY,
   double *pdStickR,
   double  rgBtn[4][3]
)
{
   double dH = (double)iHeight;
   double dW = (double)iWidth;
   double dR = dH * 0.155;
   double dBtnR = dH * 0.072;
   double dMarginX = dBtnR * 1.7;
   double dMarginY = dBtnR * 1.7;

   if (pdStickR) *pdStickR = dR;
   if (pdStickCX) *pdStickCX = dR * 1.35;
   if (pdStickCY) *pdStickCY = dH - dR * 1.35;

   rgBtn[0][0] = dW - dMarginX;              rgBtn[0][1] = dH - dMarginY;              rgBtn[0][2] = dBtnR;
   rgBtn[1][0] = dW - dMarginX - dBtnR * 2.6; rgBtn[1][1] = dH - dMarginY;              rgBtn[1][2] = dBtnR;
   rgBtn[2][0] = dW - dMarginX;              rgBtn[2][1] = dH - dMarginY - dBtnR * 2.6; rgBtn[2][2] = dBtnR;
   rgBtn[3][0] = dW - dMarginX - dBtnR * 2.6; rgBtn[3][1] = dH - dMarginY - dBtnR * 2.6; rgBtn[3][2] = dBtnR;
}

static VOID
PAL_JSApplyDirection(
   double dx,
   double dy
)
{
   double mag = sqrt(dx * dx + dy * dy);

   if (mag < g_dJSR * 0.30)
   {
      g_InputState.dir = kDirUnknown;
      return;
   }

   if (fabs(dx) > fabs(dy))
   {
      if (dx > 0.0)
      {
         g_InputState.dir = kDirEast;
         g_InputState.dwKeyPress |= kKeyRight;
      }
      else
      {
         g_InputState.dir = kDirWest;
         g_InputState.dwKeyPress |= kKeyLeft;
      }
   }
   else
   {
      if (dy > 0.0)
      {
         g_InputState.dir = kDirSouth;
         g_InputState.dwKeyPress |= kKeyDown;
      }
      else
      {
         g_InputState.dir = kDirNorth;
         g_InputState.dwKeyPress |= kKeyUp;
      }
   }
}

static VOID
PAL_JSButtonDown(
   int iButton
)
{
   switch (iButton)
   {
   case 0:
      g_InputState.dwKeyPress |= kKeySearch;
      break;

   case 1:
      g_InputState.dwKeyPress |= kKeyMenu;
      break;

   case 2:
      if (gpGlobals->fInBattle)
      {
         g_InputState.dwKeyPress |= kKeyAuto;
      }
      else
      {
         g_InputState.dwKeyPress |= kKeyUseItem;
      }
      break;

   case 3:
      g_InputState.dwKeyPress |= kKeyDefend;
      break;
   }
}

//
// 返回 TRUE 表示事件已被摇杆/按钮处理
//
static BOOL
PAL_JSHandleEvent(
   const SDL_Event *lpEvent
)
{
   double mx, my;
   int    i, w, h;
   double best;

   if (lpEvent->type != SDL_MOUSEBUTTONDOWN &&
       lpEvent->type != SDL_MOUSEBUTTONUP &&
       lpEvent->type != SDL_MOUSEMOTION)
   {
      return FALSE;
   }

   if (!g_fJSHooked)
   {
      if (SDL_GetRendererOutputSize(gpRenderer, &w, &h) == 0)
      {
         PAL_GetTouchLayout(w, h, &g_dJSCX, &g_dJSCY, &g_dJSR, g_dJSBtn);
         g_fJSHooked = TRUE;
      }
      else
      {
         return FALSE;
      }
   }

   mx = (lpEvent->type == SDL_MOUSEMOTION) ? lpEvent->motion.x : lpEvent->button.x;
   my = (lpEvent->type == SDL_MOUSEMOTION) ? lpEvent->motion.y : lpEvent->button.y;

   if (lpEvent->type == SDL_MOUSEBUTTONDOWN)
   {
      //
      // 左半屏 -> 摇杆；右半屏 -> 按钮
      //
      if (mx < g_dJSCX + g_dJSR * 2.4)
      {
         g_fStickActive = TRUE;
         g_dStickDX = mx - g_dJSCX;
         g_dStickDY = my - g_dJSCY;
         PAL_JSApplyDirection(g_dStickDX, g_dStickDY);
         return TRUE;
      }

      best = g_dJSBtn[0][2] * 1.45;
      for (i = 0; i < JS_BTN_COUNT; i++)
      {
         double dx = mx - g_dJSBtn[i][0];
         double dy = my - g_dJSBtn[i][1];
         double d = sqrt(dx * dx + dy * dy);

         if (d < g_dJSBtn[i][2] * 1.45 && d < best * 1.45)
         {
            g_iPressedButton = i;
            PAL_JSButtonDown(i);
            return TRUE;
         }
      }
      return TRUE;
   }

   if (lpEvent->type == SDL_MOUSEMOTION)
   {
      if (g_fStickActive)
      {
         double dx = mx - g_dJSCX;
         double dy = my - g_dJSCY;
         double mag = sqrt(dx * dx + dy * dy);

         if (mag > g_dJSR)
         {
            dx = dx * g_dJSR / mag;
            dy = dy * g_dJSR / mag;
         }
         g_dStickDX = dx;
         g_dStickDY = dy;
         PAL_JSApplyDirection(dx, dy);
         return TRUE;
      }
      return FALSE;
   }

   //
   // MOUSEBUTTONUP
   //
   if (g_fStickActive)
   {
      g_fStickActive = FALSE;
      g_dStickDX = 0.0;
      g_dStickDY = 0.0;
      g_InputState.dir = kDirUnknown;
      return TRUE;
   }
   if (g_iPressedButton >= 0)
   {
      g_iPressedButton = -1;
      return TRUE;
   }
   return FALSE;
}
/* ===== end joystick touch ===== */
'''

VIDEO_CODE = r'''
/* ===== joystick overlay (patched) ===== */
static SDL_Texture *gpJSBaseTex = NULL;
static SDL_Texture *gpJSKnobTex = NULL;
static SDL_Texture *gpJSBtnTex  = NULL;
static BOOL         g_fJSOverlayReady = FALSE;

static SDL_Texture *
PAL_JS_MakeCircle(
   int   iSize,
   Uint8 r,
   Uint8 g,
   Uint8 b,
   Uint8 a,
   BOOL  fFilled
)
{
   SDL_Surface *surf;
   Uint32      color;
   int         x, y;
   SDL_Texture *tex;

   surf = SDL_CreateRGBSurfaceWithFormat(0, iSize, iSize, 32, SDL_PIXELFORMAT_RGBA32);
   if (surf == NULL) return NULL;

   SDL_FillRect(surf, NULL, SDL_MapRGBA(surf->format, 0, 0, 0, 0));

   for (y = 0; y < iSize; y++)
   {
      for (x = 0; x < iSize; x++)
      {
         double dx = (x - iSize / 2.0) / (iSize / 2.0);
         double dy = (y - iSize / 2.0) / (iSize / 2.0);
         double d  = sqrt(dx * dx + dy * dy);

         if (fFilled)
         {
            if (d <= 0.98)
            {
               color = SDL_MapRGBA(surf->format, r, g, b, a);
               ((Uint32 *)((Uint8 *)surf->pixels + y * surf->pitch))[x] = color;
            }
         }
         else
         {
            if (d <= 1.0 && d >= 0.80)
            {
               color = SDL_MapRGBA(surf->format, r, g, b, a);
               ((Uint32 *)((Uint8 *)surf->pixels + y * surf->pitch))[x] = color;
            }
         }
      }
   }

   tex = SDL_CreateTextureFromSurface(gpRenderer, surf);
   SDL_FreeSurface(surf);
   if (tex != NULL)
   {
      SDL_SetTextureBlendMode(tex, SDL_BLENDMODE_BLEND);
   }
   return tex;
}

VOID
PAL_JS_DrawOverlay(
   VOID
)
{
   int      w = 0, h = 0, i;
   double   cx, cy, r;
   double   rgBtn[4][3];
   SDL_Rect dst;

   if (SDL_GetRendererOutputSize(gpRenderer, &w, &h) != 0 || w <= 0 || h <= 0)
   {
      return;
   }

   if (!g_fJSOverlayReady)
   {
      gpJSBaseTex = PAL_JS_MakeCircle(256, 255, 255, 255, 90, FALSE);
      gpJSKnobTex = PAL_JS_MakeCircle(128, 255, 255, 255, 140, TRUE);
      gpJSBtnTex  = PAL_JS_MakeCircle(128, 255, 255, 255, 110, FALSE);
      g_fJSOverlayReady = TRUE;
   }

   PAL_GetTouchLayout(w, h, &cx, &cy, &r, rgBtn);

   // 摇杆底座
   dst.w = (int)(r * 2.0);
   dst.h = (int)(r * 2.0);
   dst.x = (int)(cx - r);
   dst.y = (int)(cy - r);
   if (gpJSBaseTex) SDL_RenderCopy(gpRenderer, gpJSBaseTex, NULL, &dst);

   // 摇杆头
   {
      double kx = cx + (g_fStickActive ? g_dStickDX : 0.0);
      double ky = cy + (g_fStickActive ? g_dStickDY : 0.0);
      int    kr = (int)(r * 0.46);

      dst.w = kr * 2;
      dst.h = kr * 2;
      dst.x = (int)(kx - kr);
      dst.y = (int)(ky - kr);
      if (gpJSKnobTex) SDL_RenderCopy(gpRenderer, gpJSKnobTex, NULL, &dst);
   }

   // 四个按钮
   for (i = 0; i < 4; i++)
   {
      int br = (int)rgBtn[i][2];

      dst.w = br * 2;
      dst.h = br * 2;
      dst.x = (int)(rgBtn[i][0] - br);
      dst.y = (int)(rgBtn[i][1] - br);

      if (gpJSBtnTex)
      {
         SDL_SetTextureAlphaMod(gpJSBtnTex, (g_iPressedButton == i) ? 230 : 110);
         SDL_RenderCopy(gpRenderer, gpJSBtnTex, NULL, &dst);
      }
   }
   if (gpJSBtnTex) SDL_SetTextureAlphaMod(gpJSBtnTex, 110);
}
/* ===== end joystick overlay ===== */
'''


def read(path):
    with io.open(path, 'r', encoding='utf-8', errors='surrogateescape') as f:
        return f.read()


def write(path, text):
    with io.open(path, 'w', encoding='utf-8', errors='surrogateescape', newline='\n') as f:
        f.write(text)


def main():
    root = os.path.abspath(SRC)
    os.chdir(root)
    print('touch patch target: %s' % root)

    # ---------- input.c ----------
    text = read('input.c')
    if MARKER_INPUT not in text:
        fname = 'PAL_MouseEventFilter('
        idx = text.find(fname)
        if idx < 0:
            raise SystemExit('input.c: PAL_MouseEventFilter not found')
        # 往前找到该函数的 "static VOID" 声明行，插在它之前（不能插进签名中间）
        decl = text.rfind('static VOID', 0, idx)
        if decl < 0:
            raise SystemExit('input.c: static VOID declaration not found')
        text = text[:decl] + INPUT_CODE + '\n' + text[decl:]

        # 在鼠标处理函数开头拦下事件
        anchor2 = '   if (lpEvent->type!= SDL_MOUSEBUTTONDOWN && lpEvent->type != SDL_MOUSEBUTTONUP)\n      return;'
        idx2 = text.find(anchor2)
        if idx2 < 0:
            raise SystemExit('input.c: mouse event type check not found')
        hook = '   if (PAL_JSHandleEvent(lpEvent)) return;\n\n'
        text = text[:idx2] + hook + text[idx2:]
        write('input.c', text)
        print('  patched input.c')
    else:
        print('  skip input.c')

    # ---------- input.h ----------
    text = read('input.h')
    if 'PAL_GetTouchLayout' not in text:
        anchor = 'extern volatile PALINPUTSTATE g_InputState;'
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('input.h: g_InputState extern not found')
        end = idx + len(anchor)
        add = (
            '\n\n// joystick overlay shared state (patched)\n'
            'VOID PAL_GetTouchLayout(int iWidth, int iHeight, double *pdStickCX,\n'
            '   double *pdStickCY, double *pdStickR, double rgBtn[4][3]);\n'
            'extern BOOL   g_fStickActive;\n'
            'extern double g_dStickDX;\n'
            'extern double g_dStickDY;\n'
            'extern int    g_iPressedButton;\n'
            'VOID PAL_JS_DrawOverlay(VOID);\n'
        )
        text = text[:end] + add + text[end:]
        write('input.h', text)
        print('  patched input.h')
    else:
        print('  skip input.h')

    # ---------- video.c ----------
    text = read('video.c')
    if MARKER_VIDEO not in text:
        # 代码块插到 VIDEO_UpdateScreen 之前
        anchor = 'VOID\nVIDEO_UpdateScreen('
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('video.c: VIDEO_UpdateScreen not found')
        text = text[:idx] + VIDEO_CODE + '\n' + text[idx:]

        # 在 RenderPresent 之前绘制覆盖层
        anchor2 = 'SDL_RenderPresent(gpRenderer);'
        idx2 = text.find(anchor2)
        if idx2 < 0:
            raise SystemExit('video.c: SDL_RenderPresent not found')
        draw = '\tif (gConfig.fUseTouchOverlay) PAL_JS_DrawOverlay();\n\t'
        text = text[:idx2] + draw + text[idx2:]
        write('video.c', text)
        print('  patched video.c')
    else:
        print('  skip video.c')

    print('done.')


if __name__ == '__main__':
    main()
