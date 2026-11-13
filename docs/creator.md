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

## Dialogue

The **Dialogue** tab lists every conversation in the game. Search by a word, a
speaker or a name. A star marks a conversation you made and a pencil one you reworded.

- **Reword a game line.** Choose a conversation, choose a page, and type. The line
  may be shorter or longer than the game's. **Restore the game's wording** puts it
  back. Pages marked *Kept as it is* are steps the game runs or speech that fills in
  a number or a name; they are shown and never changed.
- **Write a conversation.** **New conversation** makes one with a single page.
  **Add page**, **Duplicate page**, **Delete page**, **Move up** and **Move down**
  shape it, and **Portrait** picks the face shown beside each page from the Library,
  or none. **Duplicate as my own** copies any conversation, including one of the
  game's, into one you can change freely.
- **Marks in the text.** A new line in the box is a new line in the game. `{page}`
  starts a new window after the player presses A. `{08:02}` and `{08:07}` are the two ink codes
  the game's own lines use; no other is accepted. `{{` is a plain brace. **Box** places the box at
  the top, middle or bottom of the screen.
- **Preview.** The right side draws the page with the game's own letters, wrapped
  where the game wraps and split where the game stops for A. Step through the
  windows with the two buttons. The frame, its colours and where the box sits are
  described in words under the preview, not drawn.
- **Remembering.** A conversation of yours can remember a named flag when it ends,
  and say another of your conversations once that flag is remembered. With no flag
  it can instead start from a later page the next time. The flag gets a number the
  base game does not use.
- **Who says it.** In **Maps**, under **Characters**, the chosen character shows
  what it says and how many others say the same. **Choose conversation** gives it any
  conversation; **Give this character their own copy** makes a copy only it says.

Dialogue changes are saved to the project as you make them, and **Undo** and **Redo**
step through them while the Dialogue tab is showing. The bottom of the tab says how
much of the room for authored dialogue is used.

## Events

The **Events** tab builds what happens in the game from steps. Nothing is typed as code.

- **An event starts** when the player talks to a character, enters a map, leaves a
  map, or walks into a region. A region is set off each time the player walks in, the
  first time on each visit, or when A is pressed inside it. Draw it in **Maps** with
  the **Events** tool.
- **Steps** are added from the list on the right: Say, Ask with two choices, If and
  Else on a flag, on the last answer or on gear the player holds, Set and Clear flag,
  Give and Take item, Open and Close passage. An If arrives with its End If, and the
  steps inside are indented. A step shown with a lock has not been seen working in
  the running game and is not built.
- **Flags** are named. **Story** lists every flag, what sets it and what reads it, and
  marks a flag nothing sets or nothing reads. A flag keeps its place in the save
  file when it is renamed, and a deleted flag's place is never given to another.
- **Who is there.** In **Maps**, under **Characters**, **Appears when** puts a
  character on the map always, only while a flag is set, or only while it is not.
  **Choose conversation or event** makes talking to the character run an event.
- **Passages.** Open passage and Close passage take a rectangle. Drag it on the map
  with the **Events** tool and choose the step it belongs to.
- **Characters.** Walk to, Face, Face toward, Wait and Do together are added like any
  other step. Choose the character from a list that starts with Player; the characters
  of the event's map follow. Walk to takes a point in pixels and a speed: Normal, Slow
  or Fast. Face toward turns a character toward another one and needs both positions
  known, which a Walk to earlier in the event gives. Wait counts frames. A Do together
  holds two or more Walk to and Face steps that run at once, and arrives with its End
  together, as an If arrives with its End If. Lie down and Stand up move the player
  only: he stays down until an event stands him up, so an event that lies him down
  has to stand him up on every path, or the build says so. Click or drag on the map
  with the **Events** tool and choose a Walk target to set where a walk goes. A walk
  ignores walls and always arrives, and the player cannot move while a character step
  runs.
- **Play with trace** starts the built game and writes down each step the game
  really ran, and each flag as it changes. **Read the trace again** shows it.
- **The game's own events** can be listed and looked at. They are never changed. A
  step DragonByte Z does not understand is shown as such.
- An event for entering a map that already runs a script of the game's runs first,
  and the game's script runs after it, unchanged.

## Where things are

| What | Where |
| --- | --- |
| Your project | the folder you chose; this is the only thing you edit |
| Your names for library items | `<project>\library\names.json` |
| Library pictures | `<project>\.dragonbyte\cache\library`; safe to delete, they are made again |
| Your maps, walls, doors and characters | the `maps` folder of the project |
| Your dialogue | `<project>\dialogue\conversations.toml` |
| Your events and flags | `<project>\events\events.toml` and `<project>\story\flags.toml` |
| The trace of the last traced play | `<project>\build\<project name>.trace.txt` |
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

- The Text tab edits the game's string table (menus, names, item and quest text).
  Spoken dialogue is edited in the Dialogue tab.
- In a game conversation only the wording of plain spoken pages can change. Its
  portraits, the order of its pages, its other steps and speech that fills in a
  number or a name are kept. Duplicate it to change more.
- A few of the game's lines are spoken in more than one conversation. The page says
  how many, and rewording it changes the conversation you are in and no other.
- A conversation of yours is speech pages and one flag rule. Choices, gifts and
  branches are made in the Events tab.
- Give item and Take item work on gear, the list the game shows under Equip, and an
  item is chosen by its number. Supplies, shops, battles, music, new items and map
  variations cannot be authored yet.
- 47 flags are free for a project. More are not offered because no safe room for
  them in the save file has been established.
- In a talk event each step other than speech takes about a second of game time,
  because the game runs it as its own conversation record.
- A region set off every frame, or by A while facing one way, exists in the game
  and is not offered.
- The event for leaving a map and the chained event for entering one were each seen
  working on one map. The rule that refuses them elsewhere is the game script's own
  shape: an event is refused where that script's end cannot be found.
- A region or event drawn in Maps is undone from the Events tab.
- Character steps are Walk to, Face, Face toward, Wait, Do together, Lie down and
  Stand up. Other gestures, a gesture on a character other than the player, creating a
  character and removing one are not offered: no proven way to do them was
  established. A walk goes in a straight line through walls, so choose a target that
  makes sense.
- Two of the game's scripts set a flag whose number is worked out while playing.
  Which flags they can reach is not established, so a clash with a flag of yours
  cannot be ruled out.
- Authored dialogue has 57 containers; the tab reports the room used. A project that uses a
  conversation script or dialogue file from the command-line tools cannot also use
  the Dialogue tab.
- The copy made by "Give this character their own copy" stays in the Dialogue tab
  when the step is undone in Maps.
- The library lists what a map places. Whether a story scene brings in anything else
  is not known, and it says so.
- A character you add is a copy of one of the game's: it behaves as the original
  behaves. Its behaviour, the way it first faces and whether it
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
- New sprites are a later milestone.

## For developers

The application is `tools/creator`: `model/` holds projects, edits, recovery and
build jobs with no Qt import, and `ui/` is the Qt presentation. Validate and Build
run in a child process. From a checkout: `python -m tools.creator`. To freeze:
`pwsh scripts/build-dragonbyte-z.ps1 -Clean`, then
`pwsh scripts/smoke-dragonbyte-z-packaged.ps1`, which runs the whole loop inside the
packaged executable. `tools/dragonbyte` (the foundation shell) and
`tools/webfoot/workbench` (the beta) are deprecated reference code; the creator
application reuses the first one's Qt-free session and journal.
