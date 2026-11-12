"""像素级触屏覆盖层：把摇杆/按钮画进游戏纹理的像素缓冲。

要点：
1. 不走 SDL 纹理，绕开 iOS/SDL3 渲染路径的不确定性；
2. 布局按「游戏画面矩形」算（不是整张纹理），所以不会画到黑边上；
3. 触摸是窗口坐标，绘制是纹理坐标，用 g_dJSTexScaleX/Y 换算；
4. 透明度贴近暗黑2：底盘几乎透明，只有一圈细白边。
"""
import io
import os
import sys

MARKER = 'PAL_JS_DrawHudPixels('

CODE = r'''
/* ===== pixel joystick overlay (patched) ===== */
void PAL_JS_DrawHudPixels(Uint8 *buf, int pitch, int texW, int texH, int winW, int winH);

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
   int i;

   for (i = -1; i <= 1; i++)
   {
      double by = cy + i * rad * 0.32;
      double bx = cx - rad * 0.42;

      while (bx <= cx + rad * 0.42)
      {
         int px = (int)bx, py = (int)by;

         if (px >= 0 && py >= 0 && px < w && py < h)
         {
            JS_BlendPixel(buf + (size_t)py * (size_t)pitch + (size_t)px * 4, r, g, b, a);
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

   if (buf == NULL || pitch <= 0 || texW < 64 || texH < 64)
   {
      return;
   }

   /* 触摸(窗口) -> 绘制(纹理) 的换算系数 */
   if (winW > 0 && winH > 0)
   {
      g_dJSTexScaleX = (double)texW / (double)winW;
      g_dJSTexScaleY = (double)texH / (double)winH;
   }

   /* 布局用窗口坐标算（v15 已验证可行），绘制时再缩放到纹理空间 */
   if (!g_fJSLayoutReady && winW > 0 && winH > 0)
   {
      PAL_GetTouchLayout(winW, winH, &g_dJSCX, &g_dJSCY, &g_dJSR, g_dJSBtn);
      g_fJSLayoutReady = TRUE;
   }

   if (!g_fJSLayoutReady)
   {
      return;
   }

   {
      double s  = (winW > 0) ? ((double)texW / (double)winW) : 1.0;
      double cx = g_dJSCX * s;
      double cy = g_dJSCY * s;
      double rr = g_dJSR * s;
      double kx2, ky2;

      /* 摇杆：无填充 + 较亮的细白环，同暗黑2 */
      JS_Ring(buf, pitch, texW, texH, cx, cy, rr, rr * 0.045 + 0.9, 255, 255, 255, 150);

      /* 摇杆头：小半透明白点 */
      kx2 = cx + (g_fStickActive ? g_dStickDX * s : 0.0);
      ky2 = cy + (g_fStickActive ? g_dStickDY * s : 0.0);
      JS_Disc(buf, pitch, texW, texH, kx2, ky2, rr * 0.30, 255, 255, 255, 120);

      /* 按钮：无填充 + 细白环；按下才出现淡淡的底 */
      for (i = 0; i < 4; i++)
      {
         double bx = g_dJSBtn[i][0] * s;
         double by = g_dJSBtn[i][1] * s;
         double br = g_dJSBtn[i][2] * s;
         int    aF = (g_iPressedButton == i) ? 55 : 0;
         int    aR = (g_iPressedButton == i) ? 200 : 150;

         if (aF > 0)
         {
            JS_Disc(buf, pitch, texW, texH, bx, by, br, 0, 0, 0, aF);
         }
         JS_Ring(buf, pitch, texW, texH, bx, by, br, br * 0.06 + 0.9, 255, 255, 255, aR);

         if (i == 1 && br > 5.0)
         {
            JS_Hamburger(buf, pitch, texW, texH, bx, by, br, 255, 255, 255, 150);
         }
      }
   }
   (void)kx;
   (void)ky;
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

    # 函数定义在 VIDEO_RenderCopy 之后，前面必须有声明
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
