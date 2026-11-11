# DragonByte Z: the creator application

DragonByte Z is the Windows application for making a game on the Buu's Fury engine.
This first version does one whole loop: **Open, Edit, Save, Build, Play, Revise**. The
thing you can edit today is the game's text. No terminal, no Python, no hex.

## What you need

- `DragonByte Z.exe` and the folder it comes in. Keep them together.
- Your own retail **Dragon Ball Z: Buu's Fury (USA)** ROM. It is only ever read.
- [mGBA](https://mgba.io/) to play what you build.

## The loop

1. **Launch.** Double-click `DragonByte Z.exe`.
2. **New Project.** Choose your ROM. The dialog says whether it is the right one.
   Name the project and pick where projects are saved. The project is a folder.
3. **Edit.** Search the list on the left, pick a record, type under "Your text".
   Problems appear under the box as you type. A pencil marks records you changed;
   a lock marks records that are read-only, with the reason.
4. **Save** (Ctrl+S). Undo is Ctrl+Z, Redo is Ctrl+Y.
5. **Build** (F6). Saves, checks the project and writes a playable ROM into the
   project's `build` folder. Problems land in the Problems panel; click one to go
   to the record.
6. **Play** (F5). Starts the built ROM in mGBA. If you changed anything since the
   last build, DragonByte Z offers to build again first. The first time, it finds an
   installed mGBA or asks you where `mGBA.exe` is, and remembers it.
7. **Revise.** Close mGBA, edit, Build, Play. The application stays open throughout.

## The library

The **Library** tab shows what is in the game: 452 maps, 297 character sprites and
155 portraits, each with a picture. Pick **Maps**, **Sprites** or **Portraits**, then:

- **Search** by name or number (`map:0019`, `sprite:0002`, `Goku`).
- **Click** one to see it larger.
- **Your name.** Type a name of your own and press Enter. It shows first in the list
  and search finds it. Your names are saved in the project's `library` folder at
  once; they change nothing in the game and never make a build out of date. Clear
  the box to remove a name.
- **Where it is used** lists the links that are known: which character definitions
  use a sprite or portrait, which portraits go with a sprite, which sprites share
  artwork. Where a link has not been established, it says "not known".

The first time you open a project, the game is read and the pictures are made in the
background. Sprites and portraits appear within seconds; maps take about two minutes.
You can keep working. Pictures are kept in the project and reopen instantly. The
library only shows things; you cannot change them here.

## Where things are

| What | Where |
| --- | --- |
| Your project | the folder you chose; this is the only thing you edit |
| Your names for library items | `<project>\library\names.json` |
| Library pictures | `<project>\.dragonbyte\cache\library`; safe to delete, they are made again |
| Built ROM | `<project>\build\<project name>.gba`; an output, rebuilt every Build |
| Settings | `settings.json` in the `DragonByte Z` folder of your Windows user's local application data |
| Log | `logs/dragonbyte-z.log` in that same folder |

## If something goes wrong

- **The application closed while you had unsaved changes.** Open the project again.
  It offers to restore them.
- **"This project's Buu's Fury ROM was not found."** The ROM moved. Locate it when
  asked; the project remembers the new place.
- **A build fails.** Nothing is lost and the last good ROM is kept. Read the
  Problems panel.

## Limits of this version

- Only the game's string table (menus, names, item and quest text) is editable.
  Spoken dialogue is listed read-only.
- The library does not yet know which characters appear on which map, and says so.
- A sprite's picture is one frame. Two sprites built from several pieces show only
  their first piece.
- Giving a name is saved at once and is not part of Undo.
- Editing maps, NPCs, events, sprites and new dialogue are later milestones.

## For developers

The application is `tools/creator`: `model/` holds projects, edits, recovery and
build jobs with no Qt import, and `ui/` is the Qt presentation. Validate and Build
run in a child process. From a checkout: `python -m tools.creator`. To freeze:
`pwsh scripts/build-dragonbyte-z.ps1 -Clean`, then
`pwsh scripts/smoke-dragonbyte-z-packaged.ps1`, which runs the whole loop inside the
packaged executable. `tools/dragonbyte` (the foundation shell) and
`tools/webfoot/workbench` (the beta) are deprecated reference code; the creator
application reuses the first one's Qt-free session and journal.
