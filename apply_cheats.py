#!/usr/bin/env python3
"""
给 SDLPAL 打金手指补丁（幂等，可重复执行）。

用法: python3 apply_cheats.py <sdlpal 源码根目录>
"""

import io
import os
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else '.'

MARKER = '// ===== Cheat menu (patched in by apply_cheats.py) ====='

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

    # 3) uigame.c: system menu item
    #    NOTE: 必须放在 #if !defined(PAL_CLASSIC) 块外面，
    #    否则 PAL_CLASSIC 构建（iOS 就是）会把这一项一起编译掉。
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

    # 4) uigame.c: menu rect taller
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

    # 5) uigame.c: case 7 handler
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
        text = text + '\n' + CHEAT_CODE + '\n'
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

    # 8) battle.c: no-encounter hook
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
