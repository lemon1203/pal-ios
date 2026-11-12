#!/usr/bin/env python3
"""
给 SDLPAL 打金手指补丁（幂等，可重复执行）。

标签文字使用 Big5 编码（游戏数据是 Big5，字体走内建繁体中文字库），
这样菜单里显示的是中文而不是 ASCII。

用法: python3 apply_cheats.py <sdlpal 源码根目录>
"""

import io
import os
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else '.'

MARKER = '// ===== Cheat menu (patched in by apply_cheats.py) ====='

# 标签文字（繁体，Big5 编码）
LABELS = {
    'money_plus': u'金錢 +10000',
    'money_full': u'金錢 全滿',
    'level':      u'全員 99 級',
    'stats':      u'全員 屬性 9999',
    'heal':       u'全員 回滿',
    'items':      u'道具 全部 99',
    'walk':       u'穿牆: ',
    'encounter':  u'不遇敵: ',
    'back':       u'返回',
    'title':      u'金手指',
}
TOGGLE = {'on': u'開', 'off': u'關'}


def b5(text):
    """编码成 Big5，返回 C 字符串字面量（含转义）。"""
    try:
        raw = text.encode('big5')
    except UnicodeEncodeError:
        raw = text.encode('ascii', 'ignore')
    return ''.join('\\x%02x' % b for b in raw)


def build_b5_block():
    lines = ['// 金手指标签（Big5 编码，脚本生成）']
    for key, text in LABELS.items():
        esc = b5(text)
        n = len(text.encode('big5')) if _encodable(text) else len(esc) // 4
        lines.append('static const unsigned char b5_%s[] = "%s";' % (key, esc))
    lines.append('static const unsigned char b5_on[]  = "%s";' % b5(TOGGLE['on']))
    lines.append('static const unsigned char b5_off[] = "%s";' % b5(TOGGLE['off']))
    return '\n'.join(lines)


def _encodable(text):
    try:
        text.encode('big5')
        return True
    except UnicodeEncodeError:
        return False


CHEAT_CODE = r'''
//
// ===== Cheat menu (patched in by apply_cheats.py) =====
//
BOOL g_fCheatWalkThrough = FALSE;
BOOL g_fCheatNoEncounter = FALSE;

#define CHEAT_LABEL_SLOTS  16
static WCHAR g_rgCheatWide[CHEAT_LABEL_SLOTS][48];

static VOID PAL_CheatRefreshLabels(VOID);

__B5_DEFS__

//
// 把 Big5 字节串（可追加 ASCII 后缀）转成宽字符存进标签槽
//
static VOID
PAL_CheatSetLabelB5(
   int                  iOffset,
   const unsigned char *pBytes,
   int                  nBytes,
   const char          *szSuffix
)
{
   char   buf[96];
   int    len = nBytes;
   int    w;
   WCHAR *dst;

   if (iOffset < 0 || iOffset >= CHEAT_LABEL_SLOTS)
   {
      return;
   }

   dst = g_rgCheatWide[iOffset];

   if (len > 80)
   {
      len = 80;
   }
   memcpy(buf, pBytes, (size_t)len);

   while (szSuffix != NULL && *szSuffix != '\0' && len < 92)
   {
      buf[len++] = *szSuffix++;
   }

   w = PAL_MultiByteToWideCharCP(CP_BIG5, (LPCSTR)buf, (size_t)len, dst, 47);
   if (w <= 0)
   {
      dst[0] = 0;
      return;
   }
   if (w > 46)
   {
      w = 46;
   }
   dst[w] = 0;
}

LPCWSTR
PAL_CheatGetWord(
   int         iOffset
)
{
   static BOOL fLabelsReady = FALSE;

   if (!fLabelsReady)
   {
      PAL_CheatRefreshLabels();
      fLabelsReady = TRUE;
   }

   if (iOffset < 0 || iOffset >= CHEAT_LABEL_SLOTS)
   {
      return L"";
   }
   return g_rgCheatWide[iOffset];
}

static VOID
PAL_CheatRefreshLabels(
   VOID
)
{
   PAL_CheatSetLabelB5(0,  b5_money_plus, sizeof(b5_money_plus) - 1, NULL);
   PAL_CheatSetLabelB5(1,  b5_money_full, sizeof(b5_money_full) - 1, NULL);
   PAL_CheatSetLabelB5(2,  b5_level,      sizeof(b5_level) - 1,      NULL);
   PAL_CheatSetLabelB5(3,  b5_stats,      sizeof(b5_stats) - 1,      NULL);
   PAL_CheatSetLabelB5(4,  b5_heal,       sizeof(b5_heal) - 1,       NULL);
   PAL_CheatSetLabelB5(5,  b5_items,      sizeof(b5_items) - 1,      NULL);
   PAL_CheatSetLabelB5(6,  b5_walk,       sizeof(b5_walk) - 1,
      g_fCheatWalkThrough ? (const char *)b5_on : (const char *)b5_off);
   PAL_CheatSetLabelB5(7,  b5_encounter,  sizeof(b5_encounter) - 1,
      g_fCheatNoEncounter ? (const char *)b5_on : (const char *)b5_off);
   PAL_CheatSetLabelB5(8,  b5_back,       sizeof(b5_back) - 1,       NULL);
   PAL_CheatSetLabelB5(10, b5_title,      sizeof(b5_title) - 1,      NULL);
}

static VOID
PAL_CheatApply(
   int         iItem
)
{
   int i;

   switch (iItem)
   {
   case 0:
      gpGlobals->dwCash += 10000;
      break;

   case 1:
      gpGlobals->dwCash = 999999;
      break;

   case 2:
      for (i = 0; i <= gpGlobals->wMaxPartyMemberIndex; i++)
      {
         WORD wRole = gpGlobals->rgParty[i].wPlayerRole;
         if (wRole == 0) continue;
         gpGlobals->g.PlayerRoles.rgwLevel[wRole] = 99;
      }
      break;

   case 3:
      for (i = 0; i <= gpGlobals->wMaxPartyMemberIndex; i++)
      {
         WORD wRole = gpGlobals->rgParty[i].wPlayerRole;
         if (wRole == 0) continue;
         gpGlobals->g.PlayerRoles.rgwMaxHP[wRole]          = 9999;
         gpGlobals->g.PlayerRoles.rgwMaxMP[wRole]          = 9999;
         gpGlobals->g.PlayerRoles.rgwHP[wRole]             = 9999;
         gpGlobals->g.PlayerRoles.rgwMP[wRole]             = 9999;
         gpGlobals->g.PlayerRoles.rgwAttackStrength[wRole] = 9999;
         gpGlobals->g.PlayerRoles.rgwMagicStrength[wRole]  = 9999;
         gpGlobals->g.PlayerRoles.rgwDefense[wRole]        = 9999;
         gpGlobals->g.PlayerRoles.rgwDexterity[wRole]      = 9999;
      }
      break;

   case 4:
      for (i = 0; i <= gpGlobals->wMaxPartyMemberIndex; i++)
      {
         WORD wRole = gpGlobals->rgParty[i].wPlayerRole;
         if (wRole == 0) continue;
         gpGlobals->g.PlayerRoles.rgwHP[wRole] = gpGlobals->g.PlayerRoles.rgwMaxHP[wRole];
         gpGlobals->g.PlayerRoles.rgwMP[wRole] = gpGlobals->g.PlayerRoles.rgwMaxMP[wRole];
      }
      break;

   case 5:
      for (i = 0; i < MAX_INVENTORY; i++)
      {
         if (gpGlobals->rgInventory[i].wItem != 0)
         {
            gpGlobals->rgInventory[i].nAmount = 99;
         }
      }
      break;

   case 6:
      g_fCheatWalkThrough = !g_fCheatWalkThrough;
      PAL_CheatRefreshLabels();
      break;

   case 7:
      g_fCheatNoEncounter = !g_fCheatNoEncounter;
      PAL_CheatRefreshLabels();
      break;

   default:
      break;
   }
}

VOID
PAL_CheatMenu(
   VOID
)
{
   LPBOX       lpBox;
   WORD        wReturnValue;
   MENUITEM    rgCheatMenuItem[9];
   int         i, nMenuItem = 9;

   PAL_CheatRefreshLabels();

   for (i = 0; i < nMenuItem; i++)
   {
      rgCheatMenuItem[i].wValue    = (WORD)(i + 1);
      rgCheatMenuItem[i].wNumWord  = (WORD)(CHEAT_WORD_BASE + i);
      rgCheatMenuItem[i].fEnabled  = TRUE;
      rgCheatMenuItem[i].pos       = PAL_XY(52, 40 + i * 18);
   }

   lpBox = PAL_CreateBox(PAL_XY(40, 28), nMenuItem - 1,
      PAL_MenuTextMaxWidth(rgCheatMenuItem, nMenuItem) - 1, 0, TRUE);

   wReturnValue = PAL_ReadMenu(NULL, rgCheatMenuItem, nMenuItem, 0, MENUITEM_COLOR);

   PAL_DeleteBox(lpBox);
   VIDEO_UpdateScreen(NULL);

   if (wReturnValue == MENUITEM_VALUE_CANCELLED)
   {
      return;
   }

   if (wReturnValue - 1 == 8)
   {
      return;   // 返回
   }

   PAL_CheatApply(wReturnValue - 1);
}
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
    print('patch target: %s' % root)

    # 1) ui.h: declarations
    text = read('ui.h')
    if 'CHEAT_WORD_BASE' not in text:
        anchor = '#define SYSMENU_LABEL_SAVE'
        add = (
            '// cheat menu labels (virtual word indices, handled in text.c PAL_GetWord)\n'
            '#define CHEAT_WORD_BASE 9000\n'
            'VOID PAL_CheatMenu(VOID);\n'
            'LPCWSTR PAL_CheatGetWord(int iOffset);\n'
            'extern BOOL g_fCheatWalkThrough;\n'
            'extern BOOL g_fCheatNoEncounter;\n'
            '\n'
        )
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('ui.h: SYSMENU_LABEL_SAVE not found')
        text = text[:idx] + add + text[idx:]
        write('ui.h', text)
        print('  patched ui.h')
    else:
        print('  skip ui.h')

    # 2) text.c: PAL_GetWord returns cheat labels
    text = read('text.c')
    if 'CHEAT_WORD_BASE' not in text:
        anchor = '   return (iNumWord >= g_TextLib.nWords'
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('text.c: PAL_GetWord return statement not found')
        add = (
            '   if (iNumWord >= CHEAT_WORD_BASE && iNumWord < CHEAT_WORD_BASE + 16)\n'
            '   {\n'
            '      return PAL_CheatGetWord(iNumWord - CHEAT_WORD_BASE);\n'
            '   }\n'
            '\n'
        )
        text = text[:idx] + add + text[idx:]
        write('text.c', text)
        print('  patched text.c')
    else:
        print('  skip text.c')

    # 3) uigame.c: system menu item (outside PAL_CLASSIC guard)
    text = read('uigame.c')
    if 'CHEAT_WORD_BASE + 10' not in text:
        marker = '#endif\n   };'
        idx = text.find(marker)
        if idx < 0:
            raise SystemExit('uigame.c: end of rgSystemMenuItem array not found')
        pos = idx + len('#endif\n')
        add = (
            '#if !defined(PAL_CLASSIC)\n'
            '      { 7,      CHEAT_WORD_BASE + 10,        TRUE,     PAL_XY(53, 72 + 108) },\n'
            '#else\n'
            '      { 7,      CHEAT_WORD_BASE + 10,        TRUE,     PAL_XY(53, 72 + 90) },\n'
            '#endif\n'
        )
        text = text[:pos] + add + text[pos:]
        write('uigame.c', text)
        print('  patched uigame.c (menu item)')
    else:
        print('  skip uigame.c (menu item)')

    # 4) uigame.c: taller update rect
    text = read('uigame.c')
    if 'rect = {40, 60, 280, 160}' not in text:
        old = 'const SDL_Rect      rect = {40, 60, 280, 135};'
        if old not in text:
            raise SystemExit('uigame.c: rect declaration not found')
        text = text.replace(old, 'const SDL_Rect      rect = {40, 60, 280, 160};')
        write('uigame.c', text)
        print('  patched uigame.c (rect)')
    else:
        print('  skip uigame.c (rect)')

    # 5) uigame.c: case 7
    text = read('uigame.c')
    if 'PAL_CheatMenu();' not in text:
        anchor = '   case 2:\n      //\n      // Load game\n      //'
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('uigame.c: case 2 (load game) not found')
        add = (
            '   case 7:\n'
            '      //\n'
            '      // Cheat menu (patched)\n'
            '      //\n'
            '      PAL_CheatMenu();\n'
            '      break;\n'
            '\n'
        )
        text = text[:idx] + add + text[idx:]
        write('uigame.c', text)
        print('  patched uigame.c (case 7)')
    else:
        print('  skip uigame.c (case 7)')

    # 6) uigame.c: append cheat implementation
    text = read('uigame.c')
    if MARKER not in text:
        code = CHEAT_CODE.replace('__B5_DEFS__', build_b5_block())
        text = text + '\n' + code + '\n'
        write('uigame.c', text)
        print('  appended cheat code to uigame.c')
    else:
        print('  skip uigame.c (cheat code)')

    # 7) map.c: extern + walk-through hook
    text = read('map.c')
    if 'extern BOOL g_fCheatWalkThrough;' not in text:
        anchor = '#include "map.h"'
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('map.c: #include "map.h" not found')
        end = idx + len(anchor)
        text = text[:end] + '\n\nextern BOOL g_fCheatWalkThrough; /* cheat hook */' + text[end:]
        write('map.c', text)
        print('  patched map.c (extern)')
    else:
        print('  skip map.c (extern)')

    text = read('map.c')
    if 'if (g_fCheatWalkThrough) return FALSE;' not in text:
        fname = 'PAL_MapTileIsBlocked(\n   BYTE       x,'
        idx = text.find(fname)
        if idx < 0:
            raise SystemExit('map.c: PAL_MapTileIsBlocked not found')
        brace = text.find('{', idx)
        if brace < 0:
            raise SystemExit('map.c: opening brace not found')
        text = text[:brace + 1] + '\n   if (g_fCheatWalkThrough) return FALSE;' + text[brace + 1:]
        write('map.c', text)
        print('  patched map.c (walk through)')
    else:
        print('  skip map.c (walk through)')

    # 8) battle.c: no-encounter
    text = read('battle.c')
    if 'if (g_fCheatNoEncounter) return kBattleResultFleed;' not in text:
        anchor = 'PAL_StartBattle(\n   WORD        wEnemyTeam,'
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('battle.c: PAL_StartBattle not found')
        brace = text.find('{', idx)
        if brace < 0:
            raise SystemExit('battle.c: opening brace not found')
        text = text[:brace + 1] + '\n   if (g_fCheatNoEncounter) return kBattleResultFleed;' + text[brace + 1:]
        write('battle.c', text)
        print('  patched battle.c (no encounter)')
    else:
        print('  skip battle.c')

    print('done.')


if __name__ == '__main__':
    main()
