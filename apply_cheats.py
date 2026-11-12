#!/usr/bin/env python3
"""
给 SDLPAL 打金手指补丁（幂等，可重复执行）。

用法: python3 apply_cheats.py <sdlpal 源码根目录>
"""

import io
import os
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else '.'

CHEAT_CODE = r'''
//
// ===== Cheat menu (patched in by apply_cheats.py) =====
//
BOOL g_fCheatWalkThrough = FALSE;
BOOL g_fCheatNoEncounter = FALSE;

#define CHEAT_LABEL_SLOTS  16
static WCHAR g_rgCheatWide[CHEAT_LABEL_SLOTS][48];

static VOID
PAL_CheatSetLabel(
   int         iOffset,
   const char *szText
)
{
   int i = 0;

   if (iOffset < 0 || iOffset >= CHEAT_LABEL_SLOTS)
   {
      return;
   }

   while (szText[i] != '\0' && i < 47)
   {
      g_rgCheatWide[iOffset][i] = (WCHAR)(unsigned char)szText[i];
      i++;
   }
   g_rgCheatWide[iOffset][i] = 0;
}

LPCWSTR
PAL_CheatGetWord(
   int         iOffset
)
{
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
   PAL_CheatSetLabel(0,  "MONEY   +10000");
   PAL_CheatSetLabel(1,  "MONEY   = 999999");
   PAL_CheatSetLabel(2,  "ALL     LEVEL 99");
   PAL_CheatSetLabel(3,  "ALL     STATS 9999");
   PAL_CheatSetLabel(4,  "ALL     HP/MP FULL");
   PAL_CheatSetLabel(5,  "ITEMS   x99");
   PAL_CheatSetLabel(6,  g_fCheatWalkThrough ? "WALK THROUGH: ON" : "WALK THROUGH: OFF");
   PAL_CheatSetLabel(7,  g_fCheatNoEncounter ? "NO ENCOUNTER: ON" : "NO ENCOUNTER: OFF");
   PAL_CheatSetLabel(8,  "BACK");
   PAL_CheatSetLabel(10, "CHEAT");
}

//
// Apply a cheat. iItem: 0-based menu index.
//
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
      for (i = 0; i <= gpGlobals->g.wMaxPartyMemberIndex; i++)
      {
         WORD wRole = gpGlobals->g.rgParty[i].wPlayerRole;
         if (wRole == 0) continue;
         gpGlobals->g.PlayerRoles.rgwLevel[wRole] = 99;
      }
      break;

   case 3:
      for (i = 0; i <= gpGlobals->g.wMaxPartyMemberIndex; i++)
      {
         WORD wRole = gpGlobals->g.rgParty[i].wPlayerRole;
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
      for (i = 0; i <= gpGlobals->g.wMaxPartyMemberIndex; i++)
      {
         WORD wRole = gpGlobals->g.rgParty[i].wPlayerRole;
         if (wRole == 0) continue;
         gpGlobals->g.PlayerRoles.rgwHP[wRole] = gpGlobals->g.PlayerRoles.rgwMaxHP[wRole];
         gpGlobals->g.PlayerRoles.rgwMP[wRole] = gpGlobals->g.PlayerRoles.rgwMaxMP[wRole];
      }
      break;

   case 5:
      for (i = 0; i < MAX_INVENTORY; i++)
      {
         if (gpGlobals->g.rgInventory[i].wItem != 0)
         {
            gpGlobals->g.rgInventory[i].nAmount = 99;
         }
      }
      break;

   case 6:
      g_fCheatWalkThrough = !g_fCheatWalkThrough;
      break;

   case 7:
      g_fCheatNoEncounter = !g_fCheatNoEncounter;
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
      return;   // BACK
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


def patch(path, anchor, insert, where='before', once=True):
    text = read(path)
    if insert.strip() in text:
        print('  skip (already patched): %s' % path)
        return
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit('锚点未找到: %s\n  在 %s 里找: %r' % (path, os.path.basename(path), anchor[:60]))
    if where == 'before':
        text = text[:idx] + insert + text[idx:]
    else:
        end = idx + len(anchor)
        text = text[:end] + insert + text[end:]
    write(path, text)
    print('  patched: %s' % path)


def main():
    root = os.path.abspath(SRC)
    os.chdir(root)

    print('打金手指补丁于: %s' % root)

    # 1) ui.h: 声明 + 词表基址
    ui_h = 'ui.h'
    text = read(ui_h)
    if 'CHEAT_WORD_BASE' not in text:
        anchor = '#define SYSMENU_LABEL_SAVE'
        add = ('// cheat menu labels (virtual word indices, see text.c PAL_GetWord)\n'
               '#define CHEAT_WORD_BASE 9000\n'
               'VOID PAL_CheatMenu(VOID);\n'
               'LPCWSTR PAL_CheatGetWord(int iOffset);\n'
               'extern BOOL g_fCheatWalkThrough;\n'
               'extern BOOL g_fCheatNoEncounter;\n\n')
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('ui.h 里找不到 SYSMENU_LABEL_SAVE')
        text = text[:idx] + add + text[idx:]
        write(ui_h, text)
        print('  patched: ui.h')
    else:
        print('  skip (already patched): ui.h')

    # 2) text.c: PAL_GetWord 返回金手指标签
    patch('text.c',
          '   return (iNumWord >= g_TextLib.nWords',
          '   if (iNumWord >= CHEAT_WORD_BASE && iNumWord < CHEAT_WORD_BASE + 16)\n'
          '   {\n'
          '      return PAL_CheatGetWord(iNumWord - CHEAT_WORD_BASE);\n'
          '   }\n\n')

    # 3) uigame.c: 系统菜单加一项
    patch('uigame.c',
          '{ 6,      SYSMENU_LABEL_BATTLEMODE,    TRUE,     PAL_XY(53, 72 + 90) },',
          '      { 7,      CHEAT_WORD_BASE + 10,        TRUE,     PAL_XY(53, 72 + 108) },\n')

    # 4) uigame.c: 菜单高度 + case 分支
    patch('uigame.c',
          'const SDL_Rect      rect = {40, 60, 280, 135};',
          '', where='before', once=True)
    text = read('uigame.c')
    if 'rect = {40, 60, 280, 160}' not in text:
        text = text.replace('const SDL_Rect      rect = {40, 60, 280, 135};',
                            'const SDL_Rect      rect = {40, 60, 280, 160};')
        write('uigame.c', text)
        print('  patched: uigame.c (menu rect)')

    # 5) uigame.c: 处理菜单返回值 7
    text = read('uigame.c')
    if 'PAL_CheatMenu();' not in text:
        anchor = '   case 2:\n      //\n      // Load game\n      //'
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('uigame.c: 找不到 case 2 (Load game) 锚点')
        add = ('   case 7:\n'
               '      //\n'
               '      // Cheat menu (patched)\n'
               '      //\n'
               '      PAL_CheatMenu();\n'
               '      break;\n\n')
        text = text[:idx] + add + text[idx:]
        write('uigame.c', text)
        print('  patched: uigame.c (case 7)')

    # 6) uigame.c: 追加金手指实现（只需一次）
    text = read('uigame.c')
    if '// ===== Cheat menu (patched in by apply_cheats.py) =====' not in text:
        text = text + '\n' + CHEAT_CODE + '\n'
        write('uigame.c', text)
        print('  appended: uigame.c (cheat code)')
    else:
        print('  skip (already patched): uigame.c (cheat code)')

    # 7) map.c: 穿墙（map.c 只包含 palcommon.h/map.h，需自行声明 extern）
    text = read('map.c')
    if 'g_fCheatWalkThrough' not in text:
        anchor = '#include "map.h"'
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('map.c: 找不到 #include "map.h"')
        end = idx + len(anchor)
        text = text[:end] + '\n\nextern BOOL g_fCheatWalkThrough; // cheat hook' + text[end:]
        write('map.c', text)
        print('  patched: map.c (extern decl)')
    else:
        print('  skip (already patched): map.c (extern)')

    text = read('map.c')
    if 'if (g_fCheatWalkThrough) return FALSE;' not in text:
        anchor = '   BYTE       h,\n   LPCPALMAP  lpMap\n)\n'
        idx = text.find(anchor, text.find('PAL_MapTileIsBlocked'))
        if idx < 0:
            raise SystemExit('map.c: 找不到 PAL_MapTileIsBlocked 函数体开头')
        end = idx + len(anchor)
        # 找到随后第一个 '{'
        brace = text.find('{', end)
        if brace < 0:
            raise SystemExit('map.c: 找不到函数左花括号')
        insert = '\n   if (g_fCheatWalkThrough) return FALSE;\n'
        text = text[:brace + 1] + insert + text[brace + 1:]
        write('map.c', text)
        print('  patched: map.c (walk through)')
    else:
        print('  skip (already patched): map.c')

    # 8) battle.c: 不遇敌
    text = read('battle.c')
    if 'g_fCheatNoEncounter' not in text:
        anchor = 'PAL_StartBattle(\n   WORD        wEnemyTeam,'
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('battle.c: 找不到 PAL_StartBattle 定义')
        brace = text.find('{', idx)
        insert = '\n   if (g_fCheatNoEncounter) return kBattleResultFleed;\n'
        text = text[:brace + 1] + insert + text[brace + 1:]
        write('battle.c', text)
        print('  patched: battle.c (no encounter)')
    else:
        print('  skip (already patched): battle.c')

    print('完成。')


if __name__ == '__main__':
    main()
