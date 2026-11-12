#!/usr/bin/env python3
"""
给 SDLPAL 换成现代触屏操作：左下虚拟摇杆 + 右下 4 个圆钮。

- 布局在 PAL_SetTouchBounds() 里用窗口尺寸算好，存全局；
- 绘制用 SDL 运行时生成的圆形纹理（适配 SDL2/SDL3）；
- 摇杆：4 向 + 30% 死区；按钮：确认/菜单/自动或道具/防御。

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

/* SDL2/SDL3 事件名兼容：SDL3 把 JS_EV_MOTION 改名为 SDL_EVENT_MOUSE_MOTION */
#if SDL_VERSION_ATLEAST(3,0,0)
#  define JS_EV_MOTION SDL_EVENT_MOUSE_MOTION
#else
#  define JS_EV_MOTION SDL_MOUSEMOTION
#endif

BOOL  g_fStickActive   = FALSE;
double g_dStickDX      = 0.0;
double g_dStickDY      = 0.0;
int   g_iPressedButton = -1;

double g_dJSCX = 0.0, g_dJSCY = 0.0, g_dJSR = 0.0;
double g_dJSBtn[4][3];
BOOL   g_fJSLayoutReady = FALSE;

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

   if (pdStickR)  *pdStickR  = dR;
   if (pdStickCX) *pdStickCX = dR * 1.35;
   if (pdStickCY) *pdStickCY = dH - dR * 1.35;

   rgBtn[0][0] = dW - dMarginX;               rgBtn[0][1] = dH - dMarginY;               rgBtn[0][2] = dBtnR;
   rgBtn[1][0] = dW - dMarginX - dBtnR * 2.6; rgBtn[1][1] = dH - dMarginY;               rgBtn[1][2] = dBtnR;
   rgBtn[2][0] = dW - dMarginX;               rgBtn[2][1] = dH - dMarginY - dBtnR * 2.6; rgBtn[2][2] = dBtnR;
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
   int    i;

   if (lpEvent->type != SDL_MOUSEBUTTONDOWN &&
       lpEvent->type != SDL_MOUSEBUTTONUP &&
       lpEvent->type != JS_EV_MOTION)
   {
      return FALSE;
   }

   if (!g_fJSLayoutReady)
   {
      return FALSE;
   }

   mx = (lpEvent->type == JS_EV_MOTION) ? lpEvent->motion.x : lpEvent->button.x;
   my = (lpEvent->type == JS_EV_MOTION) ? lpEvent->motion.y : lpEvent->button.y;

   if (lpEvent->type == SDL_MOUSEBUTTONDOWN)
   {
      double sdx = mx - g_dJSCX;
      double sdy = my - g_dJSCY;

      //
      // 只在摇杆圆范围内接管（半径 1.6 倍，宽松一点好按）
      //
      if (sqrt(sdx * sdx + sdy * sdy) <= g_dJSR * 1.6)
      {
         g_fStickActive = TRUE;
         g_dStickDX = sdx;
         g_dStickDY = sdy;
         PAL_JSApplyDirection(sdx, sdy);
         return TRUE;
      }

      //
      // 按钮圆范围内接管
      //
      for (i = 0; i < JS_BTN_COUNT; i++)
      {
         double dx = mx - g_dJSBtn[i][0];
         double dy = my - g_dJSBtn[i][1];
         double d  = sqrt(dx * dx + dy * dy);

         if (d < g_dJSBtn[i][2] * 1.35)
         {
            g_iPressedButton = i;
            PAL_JSButtonDown(i);
            return TRUE;
         }
      }

      //
      // 其他区域不接管，交回原有逻辑（菜单、音量等）
      //
      return FALSE;
   }

   if (lpEvent->type == JS_EV_MOTION)
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
   SDL_Texture *tex;
   int          x, y;

   surf = SDL_CreateRGBSurfaceWithFormat(0, iSize, iSize, 32, SDL_PIXELFORMAT_RGBA32);
   if (surf == NULL)
   {
      return NULL;
   }

   SDL_LockSurface(surf);
   memset(surf->pixels, 0, (size_t)surf->pitch * (size_t)iSize);

   for (y = 0; y < iSize; y++)
   {
      Uint8 *row = (Uint8 *)surf->pixels + (size_t)y * (size_t)surf->pitch;

      for (x = 0; x < iSize; x++)
      {
         double dx = (x - iSize / 2.0) / (iSize / 2.0);
         double dy = (y - iSize / 2.0) / (iSize / 2.0);
         double d  = sqrt(dx * dx + dy * dy);
         BOOL   fSet = fFilled ? (d <= 0.98) : (d <= 1.0 && d >= 0.62);

         if (fSet)
         {
            row[x * 4 + 0] = r;
            row[x * 4 + 1] = g;
            row[x * 4 + 2] = b;
            row[x * 4 + 3] = a;
         }
      }
   }
   SDL_UnlockSurface(surf);

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
   SDL_Rect dst;
   int      i;

   if (!g_fJSLayoutReady)
   {
      return;
   }

   if (!g_fJSOverlayReady)
   {
      gpJSBaseTex = PAL_JS_MakeCircle(256, 255, 255, 255, 165, FALSE);
      gpJSKnobTex = PAL_JS_MakeCircle(128, 255, 255, 255, 215, TRUE);
      gpJSBtnTex  = PAL_JS_MakeCircle(128, 255, 255, 255, 175, FALSE);
      g_fJSOverlayReady = TRUE;
   }

   // 摇杆底座
   dst.w = (int)(g_dJSR * 2.0);
   dst.h = (int)(g_dJSR * 2.0);
   dst.x = (int)(g_dJSCX - g_dJSR);
   dst.y = (int)(g_dJSCY - g_dJSR);
   if (gpJSBaseTex) SDL_RenderCopy(gpRenderer, gpJSBaseTex, NULL, &dst);

   // 摇杆头
   {
      double kx = g_dJSCX + (g_fStickActive ? g_dStickDX : 0.0);
      double ky = g_dJSCY + (g_fStickActive ? g_dStickDY : 0.0);
      int    kr = (int)(g_dJSR * 0.46);

      dst.w = kr * 2;
      dst.h = kr * 2;
      dst.x = (int)(kx - kr);
      dst.y = (int)(ky - kr);
      if (gpJSKnobTex) SDL_RenderCopy(gpRenderer, gpJSKnobTex, NULL, &dst);
   }

   // 四个按钮
   for (i = 0; i < 4; i++)
   {
      int br = (int)g_dJSBtn[i][2];

      dst.w = br * 2;
      dst.h = br * 2;
      dst.x = (int)(g_dJSBtn[i][0] - br);
      dst.y = (int)(g_dJSBtn[i][1] - br);

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
        decl = text.rfind('static VOID', 0, idx)
        if decl < 0:
            raise SystemExit('input.c: static VOID declaration not found')
        text = text[:decl] + INPUT_CODE + '\n' + text[decl:]

        # 在鼠标事件处理里优先拦截
        anchor2 = '   if (lpEvent->type!= SDL_MOUSEBUTTONDOWN && lpEvent->type != SDL_MOUSEBUTTONUP)\n      return;'
        idx2 = text.find(anchor2)
        if idx2 < 0:
            raise SystemExit('input.c: mouse event type check not found')
        text = text[:idx2] + '   if (PAL_JSHandleEvent(lpEvent)) return;\n\n' + text[idx2:]

        # 在 PAL_SetTouchBounds 里计算布局
        anchor3 = 'PAL_SetTouchBounds('
        i3 = text.find(anchor3)
        if i3 < 0:
            raise SystemExit('input.c: PAL_SetTouchBounds not found')
        # 找到函数体第一个 '{'
        brace = text.find('{', i3)
        if brace < 0:
            raise SystemExit('input.c: PAL_SetTouchBounds body not found')
        calc = (
            '\n   PAL_GetTouchLayout((int)dwScreenWidth, (int)dwScreenHeight,\n'
            '      &g_dJSCX, &g_dJSCY, &g_dJSR, g_dJSBtn);\n'
            '   g_fJSLayoutReady = TRUE;\n'
        )
        text = text[:brace + 1] + calc + text[brace + 1:]
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
            'VOID PAL_JS_DrawOverlay(VOID);\n'
            'extern BOOL   g_fStickActive;\n'
            'extern double g_dStickDX;\n'
            'extern double g_dStickDY;\n'
            'extern int    g_iPressedButton;\n'
            'extern double g_dJSCX;\n'
            'extern double g_dJSCY;\n'
            'extern double g_dJSR;\n'
            'extern double g_dJSBtn[4][3];\n'
            'extern BOOL   g_fJSLayoutReady;\n'
        )
        text = text[:end] + add + text[end:]
        write('input.h', text)
        print('  patched input.h')
    else:
        print('  skip input.h')

    # ---------- video.c ----------
    text = read('video.c')
    if MARKER_VIDEO not in text:
        # 关掉老的 BMP 覆盖层（Y/X/B/A 箭头图），改用运行时摇杆
        overlay_anchor = 'if (gConfig.fUseTouchOverlay)\n   {\n      extern const unsigned char bmpData[];'
        if 'gConfig.fUseTouchOverlay = FALSE;' not in text:
            oi = text.find(overlay_anchor)
            if oi < 0:
                raise SystemExit('video.c: overlay creation block not found')
            line_start = text.rfind('\n', 0, oi) + 1
            text = (text[:line_start]
                    + '   gConfig.fUseTouchOverlay = FALSE; /* patched: runtime joystick replaces BMP overlay */\n'
                    + text[line_start:])

        anchor = 'VOID\nVIDEO_UpdateScreen('
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('video.c: VIDEO_UpdateScreen not found')
        text = text[:idx] + VIDEO_CODE + '\n' + text[idx:]

        anchor2 = 'SDL_RenderPresent(gpRenderer);'
        idx2 = text.find(anchor2)
        if idx2 < 0:
            raise SystemExit('video.c: SDL_RenderPresent not found')
        draw = '\tPAL_JS_DrawOverlay();\n\t'
        text = text[:idx2] + draw + text[idx2:]
        write('video.c', text)
        print('  patched video.c')
    else:
        print('  skip video.c')

    print('done.')


if __name__ == '__main__':
    main()
