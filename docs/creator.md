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
  artwork, which maps place a sprite and what a map places. Where a link has not
  been established, it says "not known".

The first time you open a project, the game is read and the pictures are made in the
background. Sprites and portraits appear within seconds; maps take about two minutes.
You can keep working. Pictures are kept in the project and reopen instantly. The
library only shows things; you cannot change them here.

## Maps

The **Maps** tab is where you make and change places. Nothing here needs a file to be
typed, a number in hexadecimal or a command line.

- **Make a map.** Pick one of the game's maps and press **New Map From This Map**.
  Give it a name. Your map starts as a copy and is marked with a star at the top of
  the list. Everything you change on it changes only your copy; the game's own map
  stays as it was. **Rename My Map** changes the name. Adding or renaming a map never
  moves another map or breaks a door that leads to it.
- **Place pieces.** A map layer is a grid of large pieces (256 by 256 pixels). Choose
  a layer and a piece on the right, then click or drag on the map.
- **Draw tiles.** Right-click any tile (8 by 8 pixels) to pick it up, then left-click
  or drag to draw it. The first tile you draw on one of the game's pieces turns that
  piece into a new piece of your own, so the game's piece is never changed.
- **Resize a layer.** Set the width and height in pieces and press **Resize layer**.
  A layer can grow; it cannot shrink.
- **Walls.** Choose **Walls** to see where the player can walk. Darkened, dotted
  ground stops the player. Choose **Block ground** or **Open ground** and drag. Tick
  **Show walls** to keep the overlay on while you use another tool. Walls are stored
  in the game's own collision format and the game's own code reads them.
- **Doors.** Choose **Doors**, drag a box where the door is, choose the map it leads
  to, then click in that map where the player arrives. To delete a door, choose it in
  the list and press **Remove / put back door**; the same button puts back one of the
  game's doors. The list says which way the player must walk for each door to open.
- **Characters.** Choose **Characters** to see everyone and everything the map
  places, drawn where it stands and listed on the right. Click a character to choose
  it; drag it to move it. **Duplicate** makes a copy beside it. To add someone new,
  search the list of the game's characters and press **Add to this map**; the copy
  appears in the middle of the view, ready to drag. **Rename** gives your copy a name
  of your own, **Change look** draws it with the sprite of any other game character, and
  **Remove / put back** takes a character off the map or returns one of the game's.
  For a copy of a character that wanders, press **Draw wander box** and drag the area
  it may walk in. The text under the list says what cannot be changed yet for the
  character you chose. Characters show as pictures once the Library has drawn them,
  and as boxes before that.

Map changes are saved to the project the moment you make them. **Undo** and **Redo**
step back and forward through them while the Maps tab is showing. **Build** and
**Play** to walk around your map.

## Where things are

| What | Where |
| --- | --- |
| Your project | the folder you chose; this is the only thing you edit |
| Your names for library items | `<project>\library\names.json` |
| Library pictures | `<project>\.dragonbyte\cache\library`; safe to delete, they are made again |
| Your maps, walls, doors and characters | the `maps` folder of the project |
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
- The library lists what a map places. Whether a story scene brings in anything else
  is not known, and it says so.
- A character you add is a copy of one of the game's: it says and does what the
  original does. Its words, its behaviour, the way it first faces and whether it
  blocks the player cannot be changed yet.
- Game objects (enemies, items, story pieces) and story-scene characters are shown on
  the map but cannot be moved, copied or removed yet.
- Some of the game's characters only appear at certain points of the story. A copy of
  one follows the same rule, and the Characters tool says which they are.
- A map holds at most 255 characters and objects.
- A sprite's picture is one frame. Two sprites built from several pieces show only
  their first piece.
- Giving a name is saved at once and is not part of Undo.
- A new map is made from one of the game's maps; there is no blank map. Up to 58
  maps can be added. A map you made cannot be deleted in this version.
- A new door opens only when the player walks the same way as the first door the
  game put on that map; the door list says which way. A map the game gave no door
  cannot have one added.
- A door the game made cannot be moved or pointed elsewhere on a map of your own;
  remove it and make a new one.
- Walls are the grid the player walks on. Each map also has a second grid whose use
  is not established yet; it is copied unchanged.
- On a few of the game's maps, several maps share one set of walls. The Walls tool
  says so before you change them.
- Map undo history is kept until you close the project.
- Events, new sprites and new dialogue are later milestones.

## For developers

The application is `tools/creator`: `model/` holds projects, edits, recovery and
build jobs with no Qt import, and `ui/` is the Qt presentation. Validate and Build
run in a child process. From a checkout: `python -m tools.creator`. To freeze:
`pwsh scripts/build-dragonbyte-z.ps1 -Clean`, then
`pwsh scripts/smoke-dragonbyte-z-packaged.ps1`, which runs the whole loop inside the
packaged executable. `tools/dragonbyte` (the foundation shell) and
`tools/webfoot/workbench` (the beta) are deprecated reference code; the creator
application reuses the first one's Qt-free session and journal.
