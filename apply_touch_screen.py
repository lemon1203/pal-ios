"""在游戏自己的 320x200 缓冲上画触屏 UI。

原理：UI 画在 gpScreenReal（游戏的画面缓冲），再由游戏原有流程缩放上屏。
所以 UI 永远在画面内，不可能落到黑边；触摸坐标反向换算到同一空间即可对齐。
"""
import io
import os
import sys

MARKER = 'PAL_JS_DrawOnScreen('

CODE = r'''
/* ===== on-screen joystick (patched) ===== */
void PAL_JS_DrawOnScreen(Uint8 *buf, int pitch, int w, int h);

static void
JS_Px(
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
}

static void
JS_Disc2(Uint8 *buf, int pitch, int w, int h, double cx, double cy, double rad,
         Uint8 r, Uint8 g, Uint8 b, int a)
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
         double dx = x - cx, dy = y - cy;

         if (dx * dx + dy * dy <= rad * rad)
         {
            JS_Px(row + (size_t)x * 4, r, g, b, a);
         }
      }
   }
}

static void
JS_Ring2(Uint8 *buf, int pitch, int w, int h, double cx, double cy, double rad,
         double thick, Uint8 r, Uint8 g, Uint8 b, int a)
{
   double rIn = rad - thick;
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
         double dx = x - cx, dy = y - cy;
         double d2 = dx * dx + dy * dy;

         if (d2 <= rad * rad && d2 >= rIn * rIn)
         {
            JS_Px(row + (size_t)x * 4, r, g, b, a);
         }
      }
   }
}

void
PAL_JS_DrawOnScreen(
   Uint8 *buf,
   int    pitch,
   int    w,
   int    h
)
{
   int i;

   if (buf == NULL || pitch <= 0 || w < 100 || h < 100)
   {
      return;
   }

   /* 触摸坐标系 = 游戏画面坐标系 */
   g_dJSScreenW = (double)w;
   g_dJSScreenH = (double)h;

   if (!g_fJSLayoutReady)
   {
      PAL_GetTouchLayout(w, h, &g_dJSCX, &g_dJSCY, &g_dJSR, g_dJSBtn);
      g_fJSLayoutReady = TRUE;
   }

   /* 按钮 */
   for (i = 0; i < 4; i++)
   {
      double bx = g_dJSBtn[i][0];
      double by = g_dJSBtn[i][1];
      double br = g_dJSBtn[i][2];
      int    aF = (g_iPressedButton == i) ? 70 : 26;
      int    aR = (g_iPressedButton == i) ? 220 : 140;

      JS_Disc2(buf, pitch, w, h, bx, by, br, 0, 0, 0, aF);
      JS_Ring2(buf, pitch, w, h, bx, by, br, 1.0, 255, 255, 255, aR);
   }

   /* 手指处的小点（全屏方向控制） */
   if (g_fStickActive)
   {
      double rr = (h < w ? h : w) * 0.022;

      JS_Disc2(buf, pitch, w, h, g_dStickTouchX, g_dStickTouchY, rr, 255, 255, 255, 120);
   }
}
/* ===== end on-screen joystick ===== */
'''


def main():
    root = sys.argv[1]
    path = os.path.join(root, 'video.c')
    with io.open(path, 'r', encoding='utf-8', errors='surrogateescape') as f:
        text = f.read()

    if MARKER in text:
        print('video.c 已有屏内 UI，跳过')
        return

    anchor = 'VOID\nVIDEO_UpdateScreen('
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit('video.c: 找不到 VIDEO_UpdateScreen')
    text = text[:idx] + CODE + '\n' + text[idx:]

    # 在把游戏画面拷进纹理之前，先在我们的 320x200 缓冲上画 UI
    hook = 'void *texture_pixels;'
    hidx = text.find(hook)
    if hidx < 0:
        raise SystemExit('video.c: 找不到 texture_pixels 声明')
    line_end = text.find('\n', hidx) + 1
    insert = (
        '\n\t{\n'
        '\t\tint jsWinW = 0, jsWinH = 0;\n'
        '\t\tSDL_GetRendererOutputSize(gpRenderer, &jsWinW, &jsWinH);\n'
        '\t\tif (jsWinW > 0 && jsWinH > 0 && gpScreenReal->w > 0 && gpScreenReal->h > 0)\n'
        '\t\t{\n'
        '\t\t\tdouble sX = (double)jsWinW / (double)gpScreenReal->w;\n'
        '\t\t\tdouble sY = (double)jsWinH / (double)gpScreenReal->h;\n'
        '\t\t\tdouble s  = (sX < sY) ? sX : sY;   /* 保持纵横比：取小的那个 */\n'
        '\t\t\tg_dJSTouchScale = s;\n'
        '\t\t\tg_dJSTouchOffX  = (jsWinW - gpScreenReal->w * s) * 0.5;\n'
        '\t\t\tg_dJSTouchOffY  = (jsWinH - gpScreenReal->h * s) * 0.5;\n'
        '\t\t}\n'
        '\t}\n'
        '\tPAL_JS_DrawOnScreen((Uint8 *)gpScreenReal->pixels, gpScreenReal->pitch,\n'
        '\t   gpScreenReal->w, gpScreenReal->h);\n'
    )
    text = text[:line_end] + insert + text[line_end:]

    with io.open(path, 'w', encoding='utf-8', newline='\n', errors='surrogateescape') as f:
        f.write(text)

    print('  patched video.c (on-screen UI)')


if __name__ == '__main__':
    main()
