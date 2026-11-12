"""像素级触屏覆盖层：直接把摇杆/按钮画进游戏纹理的像素缓冲。

不走 SDL 纹理，绕开 iOS/SDL3 渲染路径上的所有不确定性。
插到 VIDEO_RenderCopy 里 SDL_UnlockTexture 之前执行。
"""
import io
import os
import sys

MARKER = 'PAL_JS_DrawHudPixels(pixelbuf'

CODE = r'''
/* ===== pixel joystick overlay (patched) ===== */
static void
JS_BlendPixel(
   Uint8 *p,
   Uint8  r,
   Uint8  g,
   Uint8  b,
   int    a
)
{
   int na = 255 - a;

   p[0] = (Uint8)((b * a + p[0] * na) / 255);
   p[1] = (Uint8)((g * a + p[1] * na) / 255);
   p[2] = (Uint8)((r * a + p[2] * na) / 255);
   p[3] = 255;
}

static void
JS_Disc(
   Uint8 *buf,
   int    pitch,
   int    w,
   int    h,
   double cx,
   double cy,
   double rad,
   Uint8  r,
   Uint8  g,
   Uint8  b,
   int    a
)
{
   int x0 = (int)(cx - rad) - 1, x1 = (int)(cx + rad) + 1;
   int y0 = (int)(cy - rad) - 1, y1 = (int)(cy + rad) + 1;
   int x, y;

   if (x0 < 0) x0 = 0;
   if (y0 < 0) y0 = 0;
   if (x1 > w - 1) x1 = w - 1;
   if (y1 > h - 1) y1 = h - 1;

   for (y = y0; y <= y1; y++)
   {
      Uint8 *row = buf + (size_t)y * (size_t)pitch;

      for (x = x0; x <= x1; x++)
      {
         double dx = x - cx;
         double dy = y - cy;

         if (dx * dx + dy * dy <= rad * rad)
         {
            JS_BlendPixel(row + (size_t)x * 4, r, g, b, a);
         }
      }
   }
}

static void
JS_Ring(
   Uint8 *buf,
   int    pitch,
   int    w,
   int    h,
   double cx,
   double cy,
   double rad,
   double thick,
   Uint8  r,
   Uint8  g,
   Uint8  b,
   int    a
)
{
   double rOut = rad;
   double rIn  = rad - thick;
   int x0 = (int)(cx - rOut) - 1, x1 = (int)(cx + rOut) + 1;
   int y0 = (int)(cy - rOut) - 1, y1 = (int)(cy + rOut) + 1;
   int x, y;

   if (x0 < 0) x0 = 0;
   if (y0 < 0) y0 = 0;
   if (x1 > w - 1) x1 = w - 1;
   if (y1 > h - 1) y1 = h - 1;

   for (y = y0; y <= y1; y++)
   {
      Uint8 *row = buf + (size_t)y * (size_t)pitch;

      for (x = x0; x <= x1; x++)
      {
         double dx = x - cx;
         double dy = y - cy;
         double d2 = dx * dx + dy * dy;

         if (d2 <= rOut * rOut && d2 >= rIn * rIn)
         {
            JS_BlendPixel(row + (size_t)x * 4, r, g, b, a);
         }
      }
   }
}

static void
JS_Hamburger(
   Uint8 *buf,
   int    pitch,
   double cx,
   double cy,
   double rad,
   Uint8  r,
   Uint8  g,
   Uint8  b,
   int    a
)
{
   int i;

   for (i = -1; i <= 1; i++)
   {
      double by = cy + i * rad * 0.34;
      double bx = cx - rad * 0.48;

      while (bx <= cx + rad * 0.48)
      {
         int px = (int)bx, py = (int)by;

         if (px >= 0 && py >= 0)
         {
            JS_BlendPixel(buf + (size_t)py * (size_t)pitch + (size_t)px * 4, r, g, b, a);
            JS_BlendPixel(buf + (size_t)(py + 1) * (size_t)pitch + (size_t)px * 4, r, g, b, a);
         }
         bx += 1.0;
      }
   }
}

void
PAL_JS_DrawHudPixels(
   Uint8 *buf,
   int    pitch,
   int    texW,
   int    texH,
   int    winW,
   int    winH
)
{
   int    i;
   double kx, ky;
   double s;

   if (buf == NULL || pitch <= 0 || texW < 64 || texH < 64)
   {
      return;
   }

   /* 布局按窗口坐标算（触摸事件也是窗口坐标），画的时候缩到纹理空间 */
   if (!g_fJSLayoutReady && winW > 0 && winH > 0)
   {
      PAL_GetTouchLayout(winW, winH, &g_dJSCX, &g_dJSCY, &g_dJSR, g_dJSBtn);
      g_fJSLayoutReady = TRUE;
   }

   if (!g_fJSLayoutReady)
   {
      return;
   }

   s = (winW > 0) ? ((double)texW / (double)winW) : 1.0;

   /* 摇杆：深色底盘 + 细白环 */
   {
      double cx = g_dJSCX * s, cy = g_dJSCY * s, rr = g_dJSR * s;

      JS_Disc(buf, pitch, texW, texH, cx, cy, rr, 0, 0, 0, 72);
      JS_Ring(buf, pitch, texW, texH, cx, cy, rr, rr * 0.06 + 1.0, 255, 255, 255, 170);

      /* 摇杆头 */
      kx = cx + (g_fStickActive ? g_dStickDX * s : 0.0);
      ky = cy + (g_fStickActive ? g_dStickDY * s : 0.0);
      JS_Disc(buf, pitch, texW, texH, kx, ky, rr * 0.40, 255, 255, 255, 175);
      JS_Ring(buf, pitch, texW, texH, kx, ky, rr * 0.40, rr * 0.05 + 1.0, 0, 0, 0, 90);
   }

   /* 按钮：深色圆盘 + 白环；按下变亮 */
   for (i = 0; i < 4; i++)
   {
      double bx = g_dJSBtn[i][0] * s;
      double by = g_dJSBtn[i][1] * s;
      double br = g_dJSBtn[i][2] * s;
      int    aF = (g_iPressedButton == i) ? 150 : 95;
      int    aR = (g_iPressedButton == i) ? 255 : 190;

      JS_Disc(buf, pitch, texW, texH, bx, by, br, 0, 0, 0, aF);
      JS_Ring(buf, pitch, texW, texH, bx, by, br, br * 0.10 + 1.0, 255, 255, 255, aR);

      /* 菜单键（索引 1）画三条横线做记号 */
      if (i == 1 && br > 6.0)
      {
         JS_Hamburger(buf, pitch, bx, by, br, 255, 255, 255, 190);
      }
   }
}
/* ===== end pixel joystick overlay ===== */
'''


def main():
    root = sys.argv[1]
    path = os.path.join(root, 'video.c')
    with io.open(path, 'r', encoding='utf-8', errors='surrogateescape') as f:
        text = f.read()

    if MARKER in text:
        print('video.c 已有像素覆盖层，跳过')
        return

    anchor = 'VOID\nVIDEO_UpdateScreen('
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit('video.c: 找不到 VIDEO_UpdateScreen')
    text = text[:idx] + CODE + '\n' + text[idx:]

    hook = 'SDL_UnlockTexture(gpTexture);'
    hidx = text.find(hook)
    if hidx < 0:
        raise SystemExit('video.c: 找不到 SDL_UnlockTexture')
    line_start = text.rfind('\n', 0, hidx) + 1
    insert = (
        '\t{\n'
        '\t\tint jsW = texture_pitch / 4;\n'
        '\t\tint jsH = gTextureRect.y * 2 + gTextureRect.h;\n'
        '\t\tint winW = 0, winH = 0;\n'
        '\t\tSDL_GetRendererOutputSize(gpRenderer, &winW, &winH);\n'
        '\t\tif (jsW <= 0) jsW = 320;\n'
        '\t\tif (jsH <= 0) jsH = 200;\n'
        '\t\tif (winW <= 0) { winW = jsW; winH = jsH; }\n'
        '\t\tPAL_JS_DrawHudPixels((Uint8 *)texture_pixels, texture_pitch,\n'
        '\t\t   jsW, jsH, winW, winH);\n'
        '\t}\n'
    )
    text = text[:line_start] + insert + text[line_start:]

    # 函数定义在后面，往前放一个声明，避免 implicit declaration
    proto = (
        '/* pixel joystick overlay prototype (patched) */\n'
        'void PAL_JS_DrawHudPixels(Uint8 *buf, int pitch, int texW, int texH, int winW, int winH);\n\n'
    )
    anchor_rc = 'VOID\nVIDEO_RenderCopy('
    ridx = text.find(anchor_rc)
    if ridx < 0:
        raise SystemExit('video.c: 找不到 VIDEO_RenderCopy 定义')
    text = text[:ridx] + proto + text[ridx:]

    with io.open(path, 'w', encoding='utf-8', newline='\n', errors='surrogateescape') as f:
        f.write(text)

    print('  patched video.c (pixel overlay)')


if __name__ == '__main__':
    main()
