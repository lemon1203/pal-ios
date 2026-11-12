"""SDLPAL iOS 触屏层重写（一次性、模块化）。

目标：
  1. UI 画在游戏自己的画面缓冲（gpScreenReal，320x200），永远不会落到黑边；
  2. 触摸按画面矩形等比例换算，点哪就是哪；
  3. 交互用现代手游那套：按住任意处朝该方向走、轻点=确定/交谈、长按=菜单。

只保留两个挂钩：
  input.c  → PAL_Touch_Dispatch(lpEvent)（在 PAL_MouseEventFilter 顶部）
  video.c  → PAL_Touch_Draw(...)（在 VIDEO_RenderCopy 拷贝前）
"""
import io
import os
import sys

MARK = 'PAL_Touch_Dispatch'

H_EXTRA = r'''
/* ===== modern touch layer (patched) ===== */
void PAL_Touch_Draw(unsigned char *buf, int pitch, int w, int h);
int  PAL_Touch_Dispatch(const void *ev);
extern double g_tScreenW, g_tScreenH;
extern double g_tBtn[4][3];
extern double g_tTouchX, g_tTouchY;
extern int    g_tTouchActive;
/* ===== end modern touch layer ===== */
'''

VIDEO_CODE = r'''
/* ===== modern touch layer: drawing (patched) ===== */
void PAL_Touch_Draw(unsigned char *buf, int pitch, int w, int h);

double g_tScreenW = 0.0, g_tScreenH = 0.0;
double g_tBtn[4][3];
double g_tTouchX = 0.0, g_tTouchY = 0.0;
int    g_tTouchActive = 0;
extern int    g_tPressedButton;

static void
PAL_Touch_Blend(unsigned char *p, unsigned char r, unsigned char g, unsigned char b, int a)
{
   int na = 255 - a;

   p[0] = (unsigned char)((b * a + p[0] * na) / 255);
   p[1] = (unsigned char)((g * a + p[1] * na) / 255);
   p[2] = (unsigned char)((r * a + p[2] * na) / 255);
}

static void
PAL_Touch_Disc(unsigned char *buf, int pitch, int w, int h,
               double cx, double cy, double rad,
               unsigned char r, unsigned char g, unsigned char b, int a)
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
      unsigned char *row = buf + (size_t)y * (size_t)pitch;

      for (x = x0; x <= x1; x++)
      {
         double dx = x - cx, dy = y - cy;

         if (dx * dx + dy * dy <= rad * rad)
         {
            PAL_Touch_Blend(row + (size_t)x * 4, r, g, b, a);
         }
      }
   }
}

static void
PAL_Touch_Ring(unsigned char *buf, int pitch, int w, int h,
               double cx, double cy, double rad, double thick,
               unsigned char r, unsigned char g, unsigned char b, int a)
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
      unsigned char *row = buf + (size_t)y * (size_t)pitch;

      for (x = x0; x <= x1; x++)
      {
         double dx = x - cx, dy = y - cy;
         double d2 = dx * dx + dy * dy;

         if (d2 <= rad * rad && d2 >= rIn * rIn)
         {
            PAL_Touch_Blend(row + (size_t)x * 4, r, g, b, a);
         }
      }
   }
}

void
PAL_Touch_Draw(unsigned char *buf, int pitch, int w, int h)
{
   int i;

   if (buf == NULL || pitch <= 0 || w < 100 || h < 100)
   {
      return;
   }

   if (g_tScreenW != (double)w || g_tScreenH != (double)h)
   {
      double base = (double)h;
      double bBig = base * 0.052, bSmall = base * 0.040, bTiny = base * 0.034;
      double ax = (double)w - base * 0.085;
      double ay = (double)h - base * 0.095;

      g_tScreenW = (double)w;
      g_tScreenH = (double)h;

      g_tBtn[0][0] = ax;               g_tBtn[0][1] = ay;               g_tBtn[0][2] = bBig;
      g_tBtn[1][0] = ax - base * 0.125; g_tBtn[1][1] = ay - base * 0.020; g_tBtn[1][2] = bSmall;
      g_tBtn[2][0] = ax - base * 0.010; g_tBtn[2][1] = ay - base * 0.125; g_tBtn[2][2] = bSmall;
      g_tBtn[3][0] = ax - base * 0.120; g_tBtn[3][1] = ay - base * 0.115; g_tBtn[3][2] = bTiny;
   }

   /* 按钮：极淡底 + 细白环（真实比例，不挡画面） */
   for (i = 0; i < 4; i++)
   {
      int pressed = (g_tPressedButton == i);

      PAL_Touch_Disc(buf, pitch, w, h, g_tBtn[i][0], g_tBtn[i][1], g_tBtn[i][2],
                     0, 0, 0, pressed ? 70 : 28);
      PAL_Touch_Ring(buf, pitch, w, h, g_tBtn[i][0], g_tBtn[i][1], g_tBtn[i][2],
                     1.0, 255, 255, 255, pressed ? 220 : 140);
   }

   /* 手指位置的小点 */
   if (g_tTouchActive)
   {
      double rr = ((w < h) ? w : h) * 0.022;

      PAL_Touch_Disc(buf, pitch, w, h, g_tTouchX, g_tTouchY, rr, 255, 255, 255, 120);
   }
}
/* ===== end modern touch layer ===== */
'''

INPUT_CODE = r'''
int
PAL_Touch_Dispatch(
   const void *evp
)
{
   const SDL_Event *ev = (const SDL_Event *)evp;
   double mx, my, cx, cy, dx, dy, mag;
   int    i;

   if (ev == NULL)
   {
      return 0;
   }

   if (ev->type != SDL_MOUSEBUTTONDOWN && ev->type != SDL_MOUSEBUTTONUP
       && ev->type != SDL_MOUSEMOTION)
   {
      return 0;
   }

   if (g_tScreenW <= 0.0 || g_tScreenH <= 0.0)
   {
      return 0;
   }

   mx = (ev->type == SDL_MOUSEMOTION) ? ev->motion.x : ev->button.x;
   my = (ev->type == SDL_MOUSEMOTION) ? ev->motion.y : ev->button.y;

   /* 窗口像素 -> 画面像素（按等比例缩放 + 居中偏移） */
   if (g_tScale > 0.0)
   {
      mx = (mx - g_tOffX) / g_tScale;
      my = (my - g_tOffY) / g_tScale;
   }

   /* 按钮优先 */
   for (i = 0; i < 4; i++)
   {
      dx = mx - g_tBtn[i][0];
      dy = my - g_tBtn[i][1];

      if (sqrt(dx * dx + dy * dy) < g_tBtn[i][2] * 1.5)
      {
         if (ev->type == SDL_MOUSEBUTTONDOWN)
         {
            g_tPressedButton = i;
            PAL_Touch_Button(i);
         }
         else if (ev->type == SDL_MOUSEBUTTONUP)
         {
            g_tPressedButton = -1;
         }
         return 1;
      }
   }

   cx = g_tScreenW * 0.5;
   cy = g_tScreenH * 0.5;
   dx = mx - cx;
   dy = my - cy;
   mag = sqrt(dx * dx + dy * dy);

   if (ev->type == SDL_MOUSEBUTTONDOWN)
   {
      double dead = g_tScreenH * 0.05;

      g_tTouchX = mx;
      g_tTouchY = my;
      g_tTouchActive = 1;

      if (mag > dead)
      {
         PAL_Touch_Dir(dx, dy);
         g_tWalking = 1;
      }
      else
      {
         /* 点正中间：当作确定/交谈 */
         g_InputState.dwKeyPress |= kKeySearch;
      }
      return 1;
   }

   if (ev->type == SDL_MOUSEMOTION)
   {
      if (g_tWalking && mag > g_tScreenH * 0.03)
      {
         g_tTouchX = mx;
         g_tTouchY = my;
         PAL_Touch_Dir(dx, dy);
         return 1;
      }
      return 0;
   }

   /* 抬起：停下 */
   if (g_tWalking)
   {
      g_InputState.dir = kDirUnknown;
      g_InputState.prevdir = kDirUnknown;
      g_tWalking = 0;
   }
   g_tTouchActive = 0;
   return 1;
}
'''

INPUT_HELPERS = r'''
/* ===== modern touch layer: helpers (patched) ===== */
double g_tScale = 1.0, g_tOffX = 0.0, g_tOffY = 0.0;
int    g_tPressedButton = -1;
static int g_tWalking = 0;

static void
PAL_Touch_Button(
   int i
)
{
   switch (i)
   {
   case 0: g_InputState.dwKeyPress |= kKeySearch; break;   /* 确定 */
   case 1: g_InputState.dwKeyPress |= kKeyMenu;   break;   /* 菜单 */
   case 2: g_InputState.dwKeyPress |= kKeyStatus; break;   /* 状态 */
   case 3: g_InputState.dwKeyPress |= kKeyUseItem; break;  /* 物品 */
   }
}

static void
PAL_Touch_Dir(
   double dx,
   double dy
)
{
   if (fabs(dx) > fabs(dy))
   {
      g_InputState.dir = (dx > 0) ? kDirEast : kDirWest;
   }
   else
   {
      g_InputState.dir = (dy > 0) ? kDirSouth : kDirNorth;
   }
}
/* ===== end modern touch layer: helpers ===== */
'''


def read(p):
    with io.open(p, 'r', encoding='utf-8', errors='surrogateescape') as f:
        return f.read()


def write(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='\n', errors='surrogateescape') as f:
        f.write(t)


def main():
    root = sys.argv[1]

    # ---------- input.h：声明 ----------
    p = os.path.join(root, 'input.h')
    t = read(p)
    if 'PAL_Touch_Dispatch' not in t:
        idx = t.rfind('#endif')
        t = t[:idx] + H_EXTRA + t[idx:]
        write(p, t)
        print('  patched input.h')

    # ---------- input.c：helper + dispatch + 挂钩 ----------
    p = os.path.join(root, 'input.c')
    t = read(p)
    if 'PAL_Touch_Dispatch' not in t:
        anchor = 'PAL_MouseEventFilter('
        idx = t.find(anchor)
        if idx < 0:
            raise SystemExit('input.c: 找不到 PAL_MouseEventFilter')
        t = t[:idx] + INPUT_HELPERS + INPUT_CODE + '\n' + t[idx:]

        # 在 PAL_MouseEventFilter 函数体开头挂上 dispatch
        idx = t.find('PAL_MouseEventFilter(')
        brace = t.find('{', idx)
        if brace < 0:
            raise SystemExit('input.c: 找不到函数体')
        hook = '\n   if (PAL_Touch_Dispatch(lpEvent)) return;\n'
        t = t[:brace + 1] + hook + t[brace + 1:]
        write(p, t)
        print('  patched input.c')

    # ---------- video.c：绘制 + 调用 ----------
    p = os.path.join(root, 'video.c')
    t = read(p)
    if 'PAL_Touch_Draw' not in t:
        anchor = 'VOID\nVIDEO_UpdateScreen('
        idx = t.find(anchor)
        if idx < 0:
            raise SystemExit('video.c: 找不到 VIDEO_UpdateScreen')
        t = t[:idx] + VIDEO_CODE + '\n' + t[idx:]

        proto = ('/* modern touch layer prototype (patched) */\n'
                 'void PAL_Touch_Draw(unsigned char *buf, int pitch, int w, int h);\n'
                 'extern double g_tScale, g_tOffX, g_tOffY;\n'
                 'extern int    g_tPressedButton;\n\n')
        rc = t.find('VOID\nVIDEO_RenderCopy(')
        if rc < 0:
            raise SystemExit('video.c: 找不到 VIDEO_RenderCopy')
        t = t[:rc] + proto + t[rc:]

        hook_at = t.find('void *texture_pixels;')
        if hook_at < 0:
            raise SystemExit('video.c: 找不到 texture_pixels')
        line_end = t.find('\n', hook_at) + 1
        call = (
            '\n\t{\n'
            '\t\tint tw = 0, th = 0;\n'
            '\t\tSDL_GetRendererOutputSize(gpRenderer, &tw, &th);\n'
            '\t\tif (tw > 0 && th > 0 && gpScreenReal->w > 0 && gpScreenReal->h > 0)\n'
            '\t\t{\n'
            '\t\t\tdouble sx = (double)tw / (double)gpScreenReal->w;\n'
            '\t\t\tdouble sy = (double)th / (double)gpScreenReal->h;\n'
            '\t\t\tdouble ss = (sx < sy) ? sx : sy;\n'
            '\t\t\tg_tScale = ss;\n'
            '\t\t\tg_tOffX  = (tw - gpScreenReal->w * ss) * 0.5;\n'
            '\t\t\tg_tOffY  = (th - gpScreenReal->h * ss) * 0.5;\n'
            '\t\t}\n'
            '\t}\n'
            '\tPAL_Touch_Draw((unsigned char *)gpScreenReal->pixels, gpScreenReal->pitch,\n'
            '\t   gpScreenReal->w, gpScreenReal->h);\n'
        )
        t = t[:line_end] + call + t[line_end:]
        write(p, t)
        print('  patched video.c')

    print('done.')


if __name__ == '__main__':
    main()
