# Changelog

Notable changes to what a visitor or user of this project can see.

## 2026-11-13

### A pre-push gate and one instrumentation rule for runtime evidence

- `scripts/pre-push-gate.ps1` runs `tests/unit/test_local_ci_script.py`,
  `tests/unit/test_pre_merge_check.py`, `tests/unit/test_hardcoded_address_census.py`
  and `python -m tools.quality.architecture` before a push. A pass on a clean tree is
  recorded for that commit under the git directory, so a second push of the same
  commit returns at once; a failure or a modified tracked file records nothing.
- `docs/skills/mgba-runtime.md` section 10: acceptance, combat and runtime evidence
  runs use the product's own trace script, unmodified, through a `dofile` wrapper, and
  the report cites the script's path, its git blob hash and the launch command.

## 2026-11-12

### Characters walk, face and wait inside an event

- Walk to, Face, Face toward, Wait, Do together, Lie down and Stand up are steps under
  Characters in the Events tab. A character is picked by name from the event's map,
  and the build turns that name into the number the running game answers to, taken
  from the object array it emits for that map. A step can name only a character of the
  map the event runs on: one that names another map's character, or one no longer
  there, is a problem in the Events tab and is refused by the build.
- Walk to takes a point in pixels, set by clicking or dragging on the map with the
  Events tool and kept inside the event's map, and a speed of Slow (50), Normal (100)
  or Fast (200). Wait counts 1 to 255 frames, so a longer pause is two Wait steps. Do
  together runs two or more walks and faces at once and waits for all of them to finish.
- Lie down and Stand up move the player only: he stays down until an event stands him
  up, so an event that lies him down on any path without standing him up again is
  refused by name. Other gestures and gestures on other characters are not offered, and
  a Stand up with no Lie down before it does nothing.
- Face toward works out the direction when the project is built, from where both
  characters stand, and refuses the step with a message when the event cannot know
  that; a fixed direction is always available.
- The trace lists each character step in the order the game ran it, by the
  character's visible name.
- Seen in the running game: a walk is drawn frame by frame, the player cannot move
  while a character step runs, and a walk ignores walls and arrives.
  [What was measured](docs/research/EVENTS.md).
- A project written before character steps existed builds to the same image; a byte
  for byte test holds that.
- The event editor's tests open a project from a copy of the game image, so they are
  listed with the other tests that need it in `config/rom-dependent-tests.txt`, and
  the pre-merge check asks for the focused ROM run over that list when one of those
  files changes. The character step tests read no image and are left out.

### Events are built from steps, with no scripting

- An Events tab makes, names, groups, duplicates and deletes events. An event starts
  when the player talks to a character, enters a map, leaves a map, or walks into a
  region drawn on the map.
- Steps are picked from a list: Say, Ask with two choices, If and Else on a flag, on
  the answer or on gear held, Set and Clear flag, Give and Take item, Open and Close
  passage. A step not yet seen working in the running game is shown locked and is
  not built.
- Flags are named and kept in one list. A renamed flag keeps its place in the save
  file, and a deleted flag's place is never reused, so earlier saves keep their meaning.
- In Maps, a character can be set to appear only while a flag is set or not set, and
  can run an event when spoken to. An Events tool draws regions and passage
  rectangles on the map.
- An event on a map that already runs a script of the game's runs before it; the
  game's script still runs, unchanged.
- A Story view lists what sets and reads every flag. Play with trace starts the game
  and lists the steps it really ran.
- The game's own events can be looked at and are never changed.
- Seen in the running game, on a ROM built by the application: flags, gear, who is
  on the map and an opened passage were all the same after saving at a save circle,
  resetting and loading. [What was measured](docs/research/EVENTS.md).
- Give item gives gear, which the game lists under Equip. Supplies, shops, battles
  and music are not authored yet.
- The Events tab reaches the SDK through the application's model, as the other tabs do.

## 2026-11-11

### Dialogue can be reworded and new conversations written

- A Dialogue tab lists every conversation in the game with search. A spoken line is
  reworded in place, at any length the game can show, and can be restored. Rewording
  several lines at once, in any of the game's dialogue containers, leaves every other
  line as it was.
- The list of conversations is kept between refreshes, so choosing a page or a
  character no longer pauses for about a second.
- Twenty-four of the game's lines are spoken in more than one conversation. The
  page says so, and rewording one changes only the conversation being edited.
- New conversations are made, named, duplicated and deleted. Their pages are added,
  duplicated, reordered and removed, and each page takes a portrait from the Library
  or none.
- New line, new page and the game's two ink codes are written as plain marks in the text. A
  preview draws the page with the game's own letters and shows where the game wraps
  each line and where it stops for the A button. Where the box sits on screen and
  how its frame looks are stated in words, not drawn.
- A conversation can remember a named flag when it ends, and say a different
  conversation once that flag is remembered, or start from a later page the next
  time. Flags are numbered from save flags no base-game script names.
- In Maps, a chosen character shows what it says and how many other characters say
  the same. It can be given any conversation, or a copy of its own to change alone.
- Steps of a game conversation that are not plain speech, and speech that fills in
  a number or a name, are shown and kept exactly as they are.
- The tab states how much room is used: authored dialogue goes into 57 containers of
  its own and the game's seven are never rewritten. Validate refuses a code the game
  does not have, a letter it cannot draw, a missing conversation, a flag number the
  game uses, and more words than there is room for, before any ROM is made.
- Undo and Redo in the Dialogue tab will not remove a conversation a character
  still says, and a deleted conversation's flag number is not given to a new flag.

### Characters can be placed, moved, copied, restyled and removed on a map

- The Maps tab has a Characters tool. Every character and object a map places is
  drawn on the map and listed beside it. A character is moved by dragging it,
  copied with Duplicate, added from a searchable list of every different character
  in the game, renamed, given the look of any other character in the game, and removed. A
  removed base-game character can be put back. Undo and Redo cover all of it.
- A copy of a character that wanders gets a wander box of its own, moved with it and
  redrawn by dragging.
- Each chosen character states what cannot be done with it yet: a copy says and does
  what its original does, characters always block the player, and the way a
  character first faces cannot be set. Game objects such as enemies and items, and
  story-scene characters, are shown but not edited, with the reason given.
- The Library now lists the maps that place each sprite and the sprites placed on
  each map.
- A map with a door whose arrival point is set by the story no longer shows as blank.
- Proved in mGBA on ROMs built from a private copy: a moved character stands at its
  new place; copies stand, wander inside their own box, and can come from another
  map; talking to a copy opens its original's dialogue; a copy drawn with another
  sprite still talks; a removed character is gone and the rest of the map still
  works. `docs/research/MAP_OBJECTS.md` holds the evidence and what is not yet
  established.

### The creator application gains a visual map editor with collision and doors

- A Maps tab makes a new map from any of the game's 452 maps and edits it without a
  file, a hexadecimal number or a command line: place layer pieces, draw single
  tiles, resize layers, and add or remove doors by dragging a box and clicking where
  the player arrives.
- Walls can be seen and painted. The game's collision format is now established:
  every map root names two packed 256 by 256 grids of 8-pixel cells, and the player's
  movement is tested against the first. An edited grid is packed into the game's own
  container and read by the game's own code. `docs/research/COLLISION_FORMAT.md`
  holds the evidence.
- A new map keeps its place when another map is added or renamed, so doors that lead
  to it stay correct. Edits to a new map land on its own copy and never change the
  map it was made from. A project whose new maps were made before this version
  keeps every map in place the first time a map is added.
- Renaming a map either completes or changes nothing.
- A door being added is only placed by a click on its destination map; a click on
  another map takes the editor back to the destination.
- One of the game's doors can be removed from a map.
- Map edits are saved as they are made, with Undo and Redo across all of them.
- Proved in mGBA on a ROM built by the application: a door from a game map into a new
  map, a second door into another new map and a third back; painted walls stop the
  player and opened ground lets the player through.

### The creator application gains an asset library

- A Library tab shows all 452 maps, 297 character sprites and 155 portraits, each
  with a picture and the name the game gives it where it has one. A search box narrows the list;
  clicking an item shows it larger.
- You can give any item a name of your own. Names are kept in the project's
  `library` folder, change nothing in the game and never make a build out of date.
- "Where it is used" lists verified links: the character definitions that use a
  sprite or portrait, the portraits shown with a sprite, and sprites that share
  artwork. A link that has not been established is shown as "not known".
- Pictures are made once per project by a background process, kept in the project's
  local folder and reused on reopen. The source ROM is only read, and the pictures
  are never part of a build.

### DragonByte Z opens as a creator application with a complete authoring loop

- `DragonByte Z.exe` and `DragonByte Z.cmd` now start the new creator application
  (`tools/creator`). New Project takes a retail Buu's Fury ROM, says whether it is
  the right one and creates the project folder; Open Project reopens it.
- The game's text can be searched, edited, undone, redone and saved. Text the game
  cannot store is refused as it is typed, in plain words. Spoken dialogue is listed
  read-only.
- Build saves, checks and writes a playable ROM into the project's `build` folder;
  Play starts it in mGBA and offers to rebuild when the project has changed since.
  Validate and Build run in a child process, so a failure cannot close the editor.
- Every text edit is one undo step, and Ctrl+Z and Ctrl+Y work while typing in the
  text box. Undo after a save returns to the saved text. Discarding unsaved changes
  reloads the project exactly as it was saved.
- A record whose text the game cannot store keeps the selection until the text is
  fixed or restored, so nothing typed is dropped silently.
- Play starts whichever emulator you chose, with no version gate. The launch is
  recorded in the launch-site registry as a user-selected site, the same decision
  the Workbench launcher carries.
- Unsaved edits are mirrored to the project folder and offered back after a crash.
  Each one is checked against the others before it is restored, and a discard that
  cannot reload the project says so and keeps them.
  A failed or interrupted build keeps the last good ROM.
- `scripts/smoke-dragonbyte-z-packaged.ps1` now runs that whole loop inside the
  packaged executable. Usage is in `docs/creator.md`.
- The foundation shell (`tools/dragonbyte`) and the beta Workbench are deprecated
  reference code.

### The frozen conversation-script record stays copyable and picklable

- `ConversationScripts` still rebuilds its `scripts` field as read-only mappings,
  and now reduces to plain dictionaries, so a project holding it survives
  `copy.deepcopy` and `pickle` and is rebuilt with the same read-only view. A
  fixture that deep-copies a loaded project no longer fails with "cannot pickle
  'mappingproxy' object".

### The reference project's two guards hold

- The hard-coded address census now pins the lines the scene actually added: the
  entry watcher's fourteen and the `set_save_flag` effect's three, which move the
  whole-tree pair to 3,759 lines over 305 files and the enforcement pair to 1,401
  hex5 and 935 ROM-space lines over 98 files. The ledger entry names every arrived
  line, and the effect's exemption row carries its new handler and flag-byte
  constants.
- `ConversationScripts` no longer hands out its mutable `scripts` dictionary: the
  frozen project record rebuilds it as nested read-only mappings. The synthetic
  planner test is recorded as a reasoned marker exclusion, not a ROM inventory
  member, and the warps note's trailing blank line is removed.

### The creator walkthrough names the real prerequisites

- The page now states Python 3.12, the floor in `pyproject.toml` and the version the
  quick start obtains, and mGBA 0.11, which the launcher enforces by a version-prefix
  check. Every command runs from the repository root with the quick start's
  `.\.venv\Scripts\webfoot.exe`, and the page records that running it inside
  `examples/first-scene` fails with `ModuleNotFoundError`.
- The owner copies `examples/first-scene` to a folder of his own before editing and
  builds from that copy, so the tracked reference project stays clean; the revision
  paragraph no longer says the repository never changes. A build's
  `<output>.dragonbyte.json` manifest is named.
- Play no longer assumes a save the workflow does not supply. The page resolves the
  game's own name for both rows (name text slot 600, "Yemma's Office"), says how to
  reach the office from a new game and which part of the opening is not measured, and
  tells the owner to take and load an mGBA save state on the cloud platform.
- The flag observation moved below the technical-record line under a heading that
  says it is for tool developers, so the creator walkthrough asks for no typed hex.
- "406 bytes" is now stated as changed bytes inside the 8 MiB base image, with the
  16 MiB output size, so it cannot be read against the build's per-edit counts.

### Conversation-script refusals are covered

- `tests/unit/test_conversation_script.py` now exercises every refusal branch of the
  conversation-script planner that a synthetic image can reach: bad identities, an
  unaligned or out-of-image array, a non-pointer first word, an entry past the
  array's data, a body that does not decode or never terminates, an unbalanced
  effect, a record past the image, an assembler rejection, and a missing contract
  or VM. The two branches no test reaches are named in the report with their reason.

### Reference projects are a declared repository root

- `tools/quality/architecture.py` now lists `examples` among the top-level roots a
  tracked file may live under, so the reference project at `examples/first-scene`
  passes the repository's own purity check instead of failing the CI unit gate. A
  test pins the declaration and that a file under it is accepted.

### The reference scene is a project on disk, not a page to transcribe

- The scene's project is tracked at `examples/first-scene`: `project.toml`,
  `maps/authored.toml`, `maps/transitions.toml`, `dialogue/replacements.toml` and
  `dialogue/scripts.toml`. Opening the scene is opening that directory; nothing is
  extracted for it, nothing is copied out of the documentation page and no
  directory is made by hand. The only edit the creator loop needs is the sentence
  in `dialogue/replacements.toml`.
- `tests/unit/test_conversation_script.py` reads those tracked documents and fails
  if one drifts from the pinned reference, and
  `tests/integration/test_conversation_script_rom.py` builds the tracked directory
  and pins the digest it must reproduce, `F5E19618...898D`.
- The project document's build and reproduction commands now name the tracked
  directory, and validation of that documents-only project reports zero problems.

### The scene names itself the SDK's reference fixture

- The project document, the project format and the README now name the reference
  fixture: that project's four documents plus
  `tests/integration/test_conversation_script_rom.py`, which pins the body the
  project must produce, and `tests/unit/test_conversation_script.py`, which fails
  if the documents quoted in the page drift from the pinned reference. A change to
  the dialogue, script or flag domain is expected to be checked against it.
- The same lines say what the scene is not: a tooling reference, not remake
  content.

### The scene's loop, written for the person who has to run it

- The project document's walkthrough is now for a creator working without the
  instrument or a tools programmer's help: open the project, author the sentence,
  save the file, build, play, revise. It names no ROM address, no hex value and no
  repository edit: the sentence lives in one project document and that document is
  the only thing a revision touches.

### The regression probes the fixture can reach, and the two it cannot

- The station walk and the pause menu were run on the retail image and on the
  artifact with the same route, savestate and budgets. Both probes behave
  identically and their screenshots at matching frames are byte-identical, so the
  derivative changes nothing the fixture can reach.
- Battle entry and save then load are recorded as not measured, with the reason
  each. No map in the reachable component owns a factory placement on either image;
  the pause menu has no save action and every run's battery file is empty.

### The second body is reachable, not observed

- The office conversation's first body carries a forward branch into a second body
  at `0x78099F`. The project document called that execution runtime-observed; it is
  not. The instrument logs the interpreter's entry cursor, so a branch inside one
  call leaves no row, and the cursor seen at `0x087809C7` belongs to the
  conversation's entry 5, not to this body. The claim is now what it is: the branch
  makes those bytes statically reachable, they cannot be shown dead, and they are
  carried byte for byte.

### The dialogue kinds that run code, and the two this capability authors

- Four record kinds reach the VM interpreter: kind 0 runs its block directly, kinds
  1 and 4 go through `FUN_08011FD6` and then `FUN_08011F5A`, and kind 2 goes
  through `FUN_080121D8`. Only kinds 0 and 2 keep their block at a fixed field of
  the record (`+3` and `+8`), which is what this capability can locate, so a kind 1
  or 4 record is refused by name. The refusal message and the documentation said
  the engine ran no code for those kinds, which is false; they now say what the
  capability supports and why.

### A bounded run keeps its savestates in its own directory too

- The scene launcher already forced `savegamePath` into the run directory and now
  forces `savestatePath` there as well, creating `savestates/` beside `savegame/`
  and recording both in the run's `inputs.json`. Containment no longer depends on
  mGBA's default location, which a machine with a configured global savestate path
  would override.

### A build states a count, and lists offsets on request

- `webfoot build` printed every changed byte offset for every edit, so the scene's
  own log was 193 edits and the map tables alone ran to 25,344 offsets between the
  digest and the result line. The default is now a count per edit with the switch
  named in the line, and `--verbose` prints the offsets for someone who wants them.

### One route exits the office, and it is the documented one

- The scene driver's `talkexit` route ended the conversation but never left the
  room, so it is gone. `talkend` is the documented route: fourteen A presses with a
  wait between them, then a 300-frame walk north through the door. Measured twice:
  row 452 to `map:0036` at frame 2,666. The driver also gains `north` (walks the
  station for 2,400 frames) and `menu` (opens START and pages the pause menu), the
  two probes the regression checks use.

### The save-flag byte, stated where the handler puts it

- The flag byte is `save object + 0x55 + (flag >> 3)`, so flag 228 lives at
  `0x030010D9`. The pool base word `0x030010B8` is `object + 0x50` and is five
  bytes lower; reading it as the array base silently reads a different flag. The
  effect's declared evidence, the project document and the observer's own row
  label now say the arithmetic and name the pool base only as the thing it is not.

### The scene, playable from its own document

- `docs/research/FIRST_SCENE_PROJECT.md` now carries a walkthrough for someone who
  has only the retail image, mGBA and this repository: the prerequisites, the
  extract and build commands, how to open the derivative, how to walk from the
  Other World station into the office and press A at the clerk, what the box
  should show, how to change one word and rebuild, and how to watch the save flag
  with the tracked launcher. The instrumented route it names is `talkend`, the one
  that ends the conversation and leaves the room.

### A conversation script can set a save flag

- `dialogue/scripts.toml` authors the code block a conversation record runs,
  naming the runner's own word array and one entry. A dialogue record's kind
  selects a handler and four kinds reach the VM interpreter; this capability
  supports only the two whose block is a fixed field of the record (kind 0 at `+3`,
  kind 2 at `+8`), and refuses the others by name.
- `set_save_flag` is the second declared authored effect: one `push_byte` and
  native slot 29, the engine's own flag SET at `0x08004380`. Its flag number is
  bounded by the one-byte push, and the declaration states what the handler does
  to the VM stack so an injected effect provably leaves the stack as it found it.
- The body's room is measured, never authored: it runs to the next record the
  conversation's own array can select, and a body that does not fill it is
  refused, because a shorter body would leave canonical instructions reachable
  after a terminate. A stored prior body makes an image that decodes differently a
  refusal rather than a rewrite.
- A forward branch now encodes from authored mnemonics with its two-byte
  big-endian displacement written as given, which the office conversation's own
  body needs.
- The scene project gains that fourth document and its authored event:
  `docs/research/FIRST_SCENE_PROJECT.md` records the four documents, the flag
  choice with its writer scan, the re-layout the span forced, two clean-directory
  builds at `F5E196187F08AC9AEDC3256385962B1A1690E31CF5B38F96E1352DACF324898D`, and
  four bounded runs: the flag byte went `0x00` to `0x10` at frame 859, the box
  opened and ended, and the player left row 452 for `map:0036` at frame 2,666.

### The office conversation's script, measured at runtime

- Two bounded sessions on the map-only clone named what a talk touches: the
  conversation's array at `0x087809EC` (runner object `0x03007CA8`, index 3
  selecting record `0x087809B4`), and a type-0 script at `0x0878098F` that the
  engine executes on the same frame as the A press, 16 bytes long with fourteen
  free bytes after it. The instrument gained two read-only channels - the array
  read at `0x08012530` and the interpreter entry at `0x08004038` filtered to
  cursors inside the dialogue pool.
- The proposed in-place route for a flag event - making `0x087809B4` a kind-2
  record with a code block at `+8` - is measured impossible by five bytes,
  because that span is the next live page. A kind-2 record still runs a VM block
  before its text; the older claim that a conversation cannot reach a script is
  withdrawn.

### The first authored scene project, as three documents

- A scene project is now written down end to end: the office as a new map row
  from donor 35, the retail door into it retargeted, and the assistant's own
  record carrying the authored line. `docs/research/FIRST_SCENE_PROJECT.md`
  holds the three documents, the two commands and every artifact fact, including
  two clean-directory builds at
  `535EF0772BA8A1C4E292DF70A40310A506069E249F22631FECB0194BDAF3C7B6`. The
  flag-setting event is still missing and the document says which measurement
  blocks it.

### A second donor measured for a created map

- The new-map procedure was repeated against donor 35 and reached through
  `map:0036`'s own door: table base `0x0880007C`, count bound 453, authored row
  452 with key `0x99 0x02`, six changed bytes inside the canonical image, and two
  clean builds byte-identical at
  `A67ABCCEE059CCC265DE27EFE3C60FA6F191CA0E2F1F5D634E58A2F603E177B6`.
  `docs/research/MAP_NEW_AUTHORING.md` records the project, the command and every
  number.

### A per-map door inventory that names where each door leads

- `webfoot map transitions <rom> [map:NNNN]` prints the transition records a map's
  own array holds: each record's class word, its destination map resolved from the
  two-byte key the engine compares, its trigger region and its file offset. The
  canonical image answers 735 records over 348 maps, and
  `map:0036/transition:0000` resolves to `map:0035` with region
  `(104, 137)..(488, 505)`.
- `webfoot map connections` is unchanged and still reports the narrower typed-slot
  corpus. The two commands answer different questions: a map with no typed slot can
  still own doors, and `map:0035`, `map:0036` and `map:0040` are exactly that case.
- The runtime instruments, the launcher and the reference measurements behind a
  first authored scene are tracked beside the existing mGBA tooling.
- A project can now name a compressed-dialogue record by its own selector and
  decoded start, `record:<selector>:0x<start>`, so a record the registry does not
  carry can be rewritten without a code change. The anchor resolves in the base
  image and in a derivative built from it, and an anchor that names no record is
  refused rather than guessed at.

## 2026-11-10

### A LOG1 pause page with the donor's four-tab ring

- The Legacy of Goku pause page can now be built with the four-tab ring the second
  game uses: Status, Options, Items and Quests, walked with L and R in the donor's
  measured order, on top of the merged Buu sprite, dialogue and combat build.
- The page looks like the donor's: its scrolling starfield, rounded frame, raised
  header plate, labelled tab bar, shoulder, corner and scroll arrows, status portrait
  and bars, and option sliders, composed from the donor's own 8bpp art, palette and
  font. Status shows the live level, HP, EP, EXP and NEXT; the three option sliders
  step the game's real text speed, sound and music settings.
- Items lists every occupied inventory slot by the game's own item name and count
  ("2 SENZU BEANS", "1 HERB"); Quests lists the completed quests by name, with "No
  Quests Finished" when none are complete.
- Opening the page shows no white frame, and closing fades the page to black and the
  field back in, replacing the retail white flash for the pause case only; other
  transitions are unchanged.
- The Options tab ends in a SAVE GAME row that writes the game's own save file through
  the retail save routine, asking the retail "Overwrite Slot 1?" question before it
  overwrites an occupied file, because the retail pause page was the game's only save
  path.
- Leaving the page restores the field's registers, palettes and background graphics
  byte for byte.
- The Options tab ends in a Save Game row that saves through the game's own save routine,
  asking before it overwrites an occupied file.
- The image is built by `python -m tools.webfoot.pause_menu` from a private copy of the
  donor game and assembles its payload sources itself; nothing derived from that game is
  committed.

## 2026-11-09

### Dialogue palette banks follow the dialogue itself

- Scripted dialogue that opens without a button press no longer miscolours Goku, Roshi
  and Krillin for two frames. The palette banks the dialogue box, portrait and
  presentation load are now reserved from the moment the dialogue starts until it
  returns, for every dialogue route, instead of being guessed from the A button.
- When a dialogue opens, imported sprites already shown in those banks move to free
  banks before the box loads its colours. If no free bank is left (Krillin beside Goku
  and Roshi in the Kame House talk), his piece is drawn from recoloured tile copies that
  use colours already in the game's own banks or written into their unused slots, so no sprite disappears and
  none is drawn in the wrong colours. The copies and borrowed colours are cleared at the
  dialogue's first screen update. That update now lands one frame later than before
  on these openings.
- The pending palette queue moved out of the region the game's stats heap can grow
  into, to the unused space between the sprite staging window and the heap.

### Ki blast direction and walking palette flash

- Upward and downward ki blasts now travel the way the player faces; their vertical
  velocity was inverted. mGBA runs confirmed all four directions.
- Imported sprites no longer flash with wrong colours when walking starts or changes
  direction, or when a dialogue box opens and closes. Palette changes now land together
  with the sprite list, and the object palette banks the dialogue boxes load (0 to 4
  and 7) are not used for imported sprites while A is held or a dialogue is open.

## 2026-11-08

### Buu's Fury ki, damage and passive regeneration in the player's combat

- The held ki orb is hidden. Ki use asks for a request, fuses and recovers through
  Buu's Fury math, with costs of 6 (100 max) and 8 (150 max).
- Player melee and energy hits use Buu's Fury damage with carried fractional
  hit points, keeping the game's invulnerability and death handling. Enemy hits on
  the player stay native until enemy statistics are decided.
- Passive ki follows the Buu's Fury accumulator (110 per frame, +1 per landed melee
  hit) instead of the 16-frame refill. mGBA runs verified the damage carry and the
  accumulator rollover.
- An energy hit that cannot reach the Buu's Fury path (player gone or a transition) now
  does nothing instead of reaching the native applier as a raw damage value, and a
  defeated target's carried fraction is cleared.
- Not done: Buu's Fury level and stat progression, stat-point allocation and
  enemy statistical profiles are open owner decisions (stats stay fixed for now);
  the candidate is not final.

### Runtime build checks

- Classified the ARM compiler process in the launch inventory and removed an
  extra assembly-source EOF line so the branch passes the existing CI checks.
- Selected flight/landing samples match retail; a normal movement and talk
  sequence also verifies the Krillin interaction with the dialogue backport.

### Small sprite rectangles select the exact hardware size

- Corrected 8x16 and 16x8 piece size codes. The previous longest-side inference
  selected 8x32 and 32x8 hardware objects and could read adjacent tile data.
  Explicit hardware-dimension tests and captured projectile tail pixels verify
  the correction; the five measured larger cell formats stay unchanged.

### Build the character runtime with the preserved dialogue presentation

- A [runtime build command](docs/sprite-runtime.md) now compiles the approved
  character replacements, exact palette composition, scoped two-object power-up,
  donor melee geometry and ki-flight adaptation into one LOG1 candidate. It keeps
  the 22 native fallback rows and uses the existing staged writer and provenance
  manifest. Two clean builds produce identical images and manifests.
- Controlled mGBA tests cover transformation under full actor and palette
  pressure, selected combat and projectile behavior, damage tint and dialogue.
  Natural story playback and broader gameplay coverage remain outstanding.

### Sprite bank selection keeps the retail shift

- The bank helper now returns a raw palette-bank number. The retail continuation
  performs the shift into the object attribute; shifting in both places made
  every sprite use bank zero. A forced transformation run in mGBA exposed the
  problem and confirmed restored donor and native colours after the correction.

### Sprite pieces preserve tile layout, palette indices and anchors

- Piece splitting now decodes tile order before inspecting rectangular regions,
  maps each piece into its own palette slots, and writes tile order again. Split
  cells retain the donor anchor, including mirrored offsets on flipped frames.
- The corrected partition has zero blocked Goku base, Roshi or Krillin frames.
  Four Super Saiyan rows share one blocked frame; the earlier 10/14/0/4/4 counts
  below came from treating tile data as a raster and are superseded. No pixel
  colour was changed. Runtime palette allocation and composition remain pending.

### Transformation frame-law tick correction

- The payload now accounts for the tick increment before its hook, preserving the
  eighty-tick window and the intended eleven-frame order. The assembly script also
  builds this payload. Tests cover the hook's retail context and all eighty ticks;
  this correction alone does not establish gameplay behavior.
- Sprite payloads now use the shared branch encoder, which rejects calls outside
  the ARMv4T range of four MiB in either direction. The previous duplicate encoder
  accepted unreachable targets and could silently wrap the destination.

### Legacy of Goku transformation clip: the advance law as a declared seam

- The clip's advance routine derives its frame as a shift of a per-object tick, so the
  eleven-frame clip could only ever run at sixteen ticks a frame. A four-byte call over the
  routine's increment mask is now a declared patch site, and the routine that replaces the
  law is in the tree as source: frame equals the tick divided by seven, clamped to ten, with
  the tick advanced and masked exactly as retail does and the eighty-tick cap untouched. The
  multiply-by-thirty-seven and shift-by-eight form is exact for every tick the cap allows.
- No image is emitted by this change: ten of the clip's eleven frames need two draw pieces and
  a state row names one cell per facing, so applying the law waits on that structural
  question rather than on the law.
### Legacy of Goku actor-sprite import: a frame is drawn as pieces, one bank each

- The importer now splits every carried donor frame into GBA boxes of at most fifteen
  colours, by exhaustive guillotine cuts over the boxes the GBA can actually draw, so a
  frame no longer has to fit inside one sixteen-colour bank. The split is deterministic,
  a frame that cannot be split raises an error naming the cell that makes it impossible,
  and no colour is ever trimmed or remapped to force a partition.
- The budget report measures the figures this route needs: the worst piece's colour
  count, the most pieces and the most banks any one frame draws, and how many carried
  frames have no partition at all. The approved mappings read 10, 14, 0, 4 and 4 such
  frames; Roshi partitions completely (32 frames, 46 boxes of 16x16 and 36 of 16x8, at
  most three pieces and three banks in a frame).
- Cell boxes the target's own art never draws (16x16, 16x8, 8x16 and 8x8) take their two
  attribute bytes from the law that reproduces all five measured pairs exactly: the side
  exponent of the longest side, then the shape.

### Legacy of Goku actor-draw payload: the guard owns the return

- The Legacy of Goku per-frame actor draw payload now saves `lr` in its guard
  prologue (`push {r4, r5, r6, r7, lr}`) and returns the copied retail body with
  `pop {pc}` instead of `bx lr`. The payload's `bl` into the per-piece bank
  selector left the body returning to its own continuation through the clobbered
  link register, which repeated the staging tail without bound. Both exits are
  now balanced: a refusal pops the register list it pushed, returns to the caller
  through the caller's `lr`, and writes no cursor word.
- `sprite_limits.compose_payload` replaces the copied body's final `bx lr`, and
  `sprite_limits.require_guard` decodes the assembled prologue's push, pops,
  branch targets and stores and refuses one that is unbalanced or writes through
  the render context. The ROM-gated suite covers the refusal path, the link
  register round trip and the ceiling stress, and asserts the two displaced
  retail sites instead of one.

### Legacy of Goku actor-sprite import: fallback rows as data, and the per-frame palette figure

- A sprite-import target may now declare `fallback_states`: the art-state rows that keep
  the target's own art instead of donor art. Each is verified populated in the target
  image, may not also be declared as a donor state, and is reported as `LOG1-FALLBACK`.
  The twenty-two parked rows (nine for Goku base, nine for Goku Super Saiyan, two each
  for Krillin art 46 and art 47) are now in the manifests, so the state-count check
  measures the rows that actually receive donor art: five, four, two and two.
- The budget report now also prints the worst number of distinct palette indices any one
  carried frame needs, separately from the union across every carried frame. The two
  figures answer two different questions, and the per-frame one is the binding one: a
  Legacy of Goku cell names a single sixteen-colour bank, so a frame needs at most fifteen.
  Every approved mapping fails that test as well as the union one (21, 22, 21, 18 and 18
  distinct indices in one frame for Goku base, Goku Super Saiyan, Roshi and the two
  Krillin slots), which makes the colour question a decision rather than a mapping choice.
- Nothing on this route writes an image or stores a ROM byte, and no verdict moved
  towards a pass: all five manifests still report DOES NOT FIT.

### Legacy of Goku actor-sprite import: manifest, adapter and budget

- Added `python -m tools.webfoot.sprite_import <manifest> --donor-rom <path>
  --target-rom <path>`. It reads a donor image in place, builds the Legacy of Goku
  art-cell and four-bit tile payload for every carried frame, and reports each
  target resource as FITS, DOES NOT FIT or UNKNOWN with the figure and the source
  of the limit. It exits non-zero unless every check fits, so an unmeasured limit
  stops a run instead of passing it.
- Added a versioned manifest, `webfoot.sprite-import/1`, naming the donor image by
  digest, the donor definition, the carried slots with their classification, the
  target art slot and the timing class of each animation. A timing label is never
  promoted: a MEASURED row must carry the run that measured it, an ASSUMED row the
  owner's acceptance, and a PLACEHOLDER row may carry no duration at all.
- Added the five approved mappings under `config/sprite-imports/`: Goku base and
  Super Saiyan, Master Roshi, Krillin into art 46, and art 47 as a declared
  swap-in that reuses the art 46 donor art until a custom sprite is supplied. All
  five report DOES NOT FIT on palette depth and four on the target art's own state
  count; the per-frame tile ceiling is UNKNOWN because no run has measured it. No
  image is written and no ROM byte is stored in this repository.
- A built cell now carries the target image's own object size and shape bytes for its box,
  measured across every art definition in the image (16x32 is size 2 shape 2, 32x32 is size 2
  shape 0, and three more boxes are measured). A box the image does not draw, sixteen by
  sixteen among them, is refused by name rather than given a guessed pair, and an adapted
  frame list for the Legacy of Goku II donor family is now read with that family's own
  piece reader.

## 2026-11-07

### Legacy of Goku declared-scene dialogue authoring

- Added the `scene` command group. `webfoot scene init` creates a project from a
  verified original image, optionally composing a donor dialogue presentation and
  an approved dialogue file; `webfoot scene show` prints the declared scene and
  any authored text; `webfoot scene set-text` writes one node's text into the
  project's raw document. A replacement is bounded by its own slot's measured
  capacity and is refused, not relocated, when it does not fit.
- Added `webfoot donor portrait`, `webfoot donor convert` and
  `webfoot payloads plan`. A composed patch document records payload bytes with
  their pinned digests (transferred, adapted or new) plus the relative, pointer
  and hook seams that reach them, each with the original bytes it expects.
- `validate` and `build` now consume the declared scene and the derived dialogue
  node plan. The plan is re-derived during validation, so a project whose
  declared digest was recomputed over a changed table is refused before any
  image is written.
- The declared-scene route is present in an installed build, not only when
  running from a checkout. The packaged ROM profile catalogue carries the same
  declared scene and patch sites as the in-repo copy, which is what
  `webfoot scene init` resolves against once the package is installed.

## 2026-11-06

### Trilogy direction and LOG1-first application

- Reframed the repository home around the trilogy initiative, the independent
  LOG1-first application goal, the existing SDK and all three disassemblies.
- Distinguished older desktop tools from planned authoring workflows and static
  recompilation research; clarified what the existing installation guide installs.

### Repository home and developer navigation

- Preserved the explicit original-engine acceptance boundary in the landing page.
- Replaced the long landing page with a concise SDK overview, verified Workbench
  screenshots, game-specific maturity and a direct Windows setup path.
- Consolidated installation guidance, indexed research by topic and retained the
  former homepage as historical evidence. Corrected missing documentation paths
  and labelled historical status records.
- Aligned the dependency lock with the existing Qt and test-tool requirements so
  the documented locked setup succeeds. SDK behavior and ROM identities are unchanged.

### The toolkit now has an install page and a path from a clone to a verified modification

- `INSTALL.md` states the prerequisites, the install command (`scripts\setup.ps1`,
  which installs Python 3.12 through `uv` when the host has none and runs
  `uv sync --locked` with the `dev`, `workbench` and `research` extras), how to
  verify the install, and how the `webfoot` entry point behaves. It marks the
  install commands it did not run and proves `python -m tools.webfoot --help` by
  execution.
- `docs/newcomer.md` walks five stages from supported features to validation. Each
  stage is marked executed, partially executed or not executed, with its command
  and exit code. Stages that need a game image are marked NOT EXECUTED, and the
  page says it does not demonstrate a complete workflow.
- `README.md` and `docs/README.md` route a reader to those pages and to the three
  standards below.

### A change now has a stated definition of done, a source-classification rule and a naming page

- `docs/definition-of-done.md` states what a finished change is here: an output
  reproducible from pinned inputs plus a manifest that names what changed, in
  eleven criteria, each naming how it is checked. Ten name a command or test;
  the last two are enforced by review rather than by a gate.
- `docs/source-classification.md` gives the path rule that assigns every tracked
  file exactly one of twelve classes, with the count per class and a list of what
  the rule does not classify.
- `docs/naming.md` records twelve identifier conventions with the evidence for
  each, and says which a gate enforces. It states that no gate checks module,
  class or function names.

### The capability figure says what it counts, in the visible text and the accessible name

- `src/components/ProgressStrip.astro` renders the ratio as editor capabilities
  shipped, titles the window `Editor capabilities: <percent>%`, names the progress
  bar "Editor capability coverage", and adds a scope line: the figure counts
  editor capabilities only, the acceptance target has not started, and the project
  itself is not complete.
- `src/data/project.ts` extends the percentage caveat to say the figure is not a
  measure of overall project completion.
- `src/components/Hero.astro` qualifies its buildout fraction as editor
  capabilities, and `src/components/LatestWins.astro` replaces the unqualified
  "proven at runtime or byte for byte" aside with "Newest first".
- No capability state or count changes, and no product code path, ROM profile or
  `roms.yaml` pin moves.

### The built site is built and checked in the pull-request gate

- The `prepare` job in `.github/workflows/ci.yml` builds the site (`npm ci`,
  `npm run build`), runs `tools.quality.site_check`, and runs the three test files
  that carry the site-not-built guard: `tests/unit/test_site_consistency.py`,
  `tests/unit/test_capability_registry.py` and `tests/unit/test_questline_rail.py`.
  The test partitions have no built site, so those rendered-page assertions used
  to skip there.
- Against the built page, `tests/unit/test_site_consistency.py` runs 23 tests with
  none skipped, and `tests/unit/test_capability_registry.py` asserts the qualified
  ratio and the scope disclaimer instead of the old unqualified sentence.
- The site is built and checked. This GitHub workflow does not publish or deploy
  it; the separate `deploy-site` job in `.gitlab-ci.yml`, unchanged here, remains
  the only automated publishing path and runs on the default branch only. The
  tracked `wrangler.jsonc` means a person with credentials can also publish by
  hand.
- `README.md` no longer calls the public progress site "always-current". It is
  republished when the deploy job runs, and that job does not run while the
  hosting quota is spent.

### The public-surface guard catches an identifier that begins with a screened term

- `tools/quality/_public_surface_tables.py` changes the boundary on each side of
  two of its fourteen screens: an identifier that begins with a screened term is
  caught even when an underscore follows it, while a term that sits inside a
  longer identifier is still allowed. `tests/unit/test_public_surface.py` pins both
  directions for both terms.
- Measured after the change: 1,331 tracked text files scanned, 0 findings, 24
  suppressed by a written exception. The other twelve screens are unchanged.

### A census-coupled change now reports every pin it can move

- `tools/dev/ci_tier.py` gains `measurement_lines()`, which prints every address
  pin and every exemption row a change can move, not only the one a brief names.
  The gate record writes them under a `measurements` heading.
- `tests/unit/test_ci_tier.py` pins the behaviour: a catalogue change names the
  whole-tree pin, the enforcement pin and the row counts; a change outside the
  measured set reports nothing.
- It is a report, not a gate: it does not compute a new pin for the author, and it
  does not fail a change for naming one pin.

## 2026-11-05

### The 18 Legacy of Goku script families load, decode and re-encode losslessly

- `tools/webfoot/formats/script_vm.py` decodes and re-encodes the first game's
  script records. A record is an activation-count byte followed by that many
  `0x00`-terminated segments; the byte is compared against a per-call counter by
  the interpreter, so it counts activations and not frames. Every one of the 282
  distinct record starts re-encodes to the same bytes it decoded from, unknown
  bytes included, and a structure the encoding does not cover fails with a named
  error instead of being reinterpreted.
- `tools/webfoot/data/script_specs.py` registers that encoding for the Legacy of
  Goku profile with operand widths and structure only. No opcode is given a name
  or an effect, because none has been established.
- `config/roms.yaml` and its packaged duplicate declare the 18 verified script
  families. The declaration is what makes them visible to profile validation and
  to the script loader; it grants no authoring capability.
- The interpreter keeps `record + 1` as its stream pointer, so a record start and
  a stream pointer are different addresses. A stream pointer offered as a record
  is refused for all 18 families rather than decoded at the wrong boundary.
- `webfoot event show` refuses a record-grammar family with a named, informative
  error instead of failing with an unhandled `KeyError`. It displays instruction
  blocks, and these families have none; the command does not pretend the two
  formats are the same.
- Legacy of Goku II and Buu's Fury script behaviour is unchanged. The record
  layer is opt-in per profile, and both of those codecs decode the same entry,
  block and instruction counts as before.

## 2026-11-02

### PR gate runs the selected tests in four jobs

- `.github/workflows/ci.yml` no longer runs the selected tests in one job. The
  former `gate` job is now `prepare`, which keeps every step that must happen once
  - checkout, Python setup, the classifier, the digest check and the four quality
  gates - and publishes the selected tests as the `pr-gate-selection` artifact.
  Four `partition` jobs then run that one selection under the existing
  `WEBFOOT_SHARD_COUNT` and `WEBFOOT_SHARD_INDEX` variables, with
  `--max-worker-restart=0` and the duration reporting unchanged, and a `record` job
  writes the run's one verdict and names every failing node. The selection travels
  as an artifact instead of being recomputed in each job, so the four partitions
  run the same nodes the concentrated job ran and no node is run twice, and the
  run still fails when any partition fails.
- A partition that owns no node of a small selection no longer fails the gate. A
  change touching one test file can select fewer nodes than there are partitions,
  which left a partition with nothing to run; pytest reports every node deselected
  and exits 5, and that exit used to redden an otherwise green change. Such a
  partition now says so and passes. The tolerance is narrow on purpose: it applies
  only to exit 5 with a deselected summary and no failure, error or collection
  problem, so a failing test, a missing path and a crashed worker all still fail
  the gate.
- The gate record calls a partition that was cancelled or timed out a failure. It
  previously tested only for an outright failure, so an interrupted run could be
  recorded as a successful gate.

### Test timing budgets removed

- The per-test timing guard is gone. A test that ran longer than its allowance
  used to fail the run on the GitHub runner, with a table of per-node budgets and
  exceptions maintained by hand in `tests/conftest.py`. Measured on gate run
  41398167492, five tests exceeded their allowances by one to fourteen percent on
  a slower hosted runner and failed an otherwise green suite; one of them turned
  an unrelated test red, because the session exit status the guard raised is the
  value that test reads. A wall-clock measurement of a shared runner is not a
  property of the code, so it no longer decides whether the suite passes.
- Removed with it: the budget constants, the hand-maintained exception table, the
  single-node re-run that tried to tell a regression from runner variance, the
  per-test duration recording, and the eight-minute shard ceiling in the
  full-regression workflow. Shard elapsed time is still printed, and no longer
  throws.
- Execution time stays visible. Every test-suite invocation now reports its
  twenty-five slowest tests over one second: the tiered CI selection, each
  full-regression shard, the integration runs and both local scripts. The
  adjacency runner is the one deliberate exception, because its argument vector is
  pinned by equality to forbid inserted filters. A test that gets slow shows up in
  the log without failing an otherwise green run. Two time-based failure
  conditions remain, neither a hand-maintained per-test allowance: the 120-second
  per-test cap in `pyproject.toml` and the GitHub Actions job timeouts, plus the
  local gate's own 45-minute budget.

### Qt test stability

- The text-tool theme installs its proxy style once per application instead of
  once per application call. Each reinstallation handed Qt a new style and
  destroyed the one it replaced, leaving Python wrappers of the destroyed style
  behind; that churn is the lifetime defect THEME-STYLE-CRASH-001 investigates. A
  second `apply_theme` now updates the palette and stylesheet only, and a test
  requires the installed proxy to remain the same, valid object.

### The desktop data page opens and saves a one-field project

- The data surface reports a project's authored state only for the fields a
  record's own format decodes, and the editor's save path rebuilds each enemy
  record by decoding the project's raw bytes through the codec its record size
  names. Legacy of Goku II projects therefore open and save in the desktop
  editor, and a save of an unedited project builds back to the canonical image
  byte for byte.
- A project entry that names a stat field its ROM's record format does not
  decode is reported by validation instead of being dropped without a message.
  A field the record does decode is not reported, whether or not the editor can
  edit it, so a project whose records carry a type id, a person or a technique
  count still validates and builds back to the canonical image byte for byte.
- The desktop save path refuses the same authored field rather than writing the
  project without it.

### Projects and commands for a profile that declares one stat table

- `webfoot extract` writes stat records for a profile whose enemy table decodes
  only HP, and a project built from it reproduces the canonical image exactly.
  A project record carries only the fields its own format decodes, so Legacy of
  Goku II projects hold `hp` and `raw` per enemy and no field no codec produced.
- A project that authors no stat records is treated as authoring none, matching
  how absent text and map files already behave, rather than being reported as
  missing every record it never mentioned. A project that authors some records
  is still held to the full set, so a half-written extraction is caught.
- The stat and string commands no longer name a game in their headings, and a
  stat listing now says what an identity is: a type id where the record format
  carries one, otherwise the table index.
- A supplied profile is compared with the packaged contract for every stat
  table, so one that adds a table the contract does not declare is refused as
  one that drops a table.

### Stat authoring serves a profile that declares only an enemy table

- A profile that declares an enemy stat table and no character base-stat table
  is now served by the semantic stat layer and by `webfoot stats` (`list`,
  `set`, `validate-round-trip`). Reading, editing and saving Legacy of Goku II
  enemy HP runs through the same path as Buu's Fury's: the table loads, a record
  is read, an HP edit is planned, emitted and reopened. A profile that declares
  no enemy table is still refused, and the refusal names the missing
  declaration.
- The character side is empty for such a profile rather than invented:
  `characters()` yields nothing and naming a character record is refused by
  name. A profile that declares both tables is unchanged, including its nine
  named characters.
- An enemy record is named by the identity its own record format carries. Buu's
  Fury's keys on `type_id` (`enemy:434`); Legacy of Goku II's record decodes no
  type id and has no unique field at all, so its keys are table indices
  (`enemy:41`).
- Only the fields a declared record format decodes can be edited: `hp` for
  Legacy of Goku II, with any other field name refused. `webfoot stats list`
  prints the columns a format carries, so that table lists identity, index,
  offset and HP.


## 2026-11-01

### Merge evidence

- The merge tool verifies a GitHub Actions run as test evidence: named by id and
  read through the API, it must have run against the pinned commit, have
  finished, have concluded success, and every job it reports must have
  succeeded. A run reporting no jobs is refused, because a success that cannot
  be attributed to anything that ran is not evidence. A local gate record is
  still accepted for a tree whose suite is not on Actions, and one of the two is
  required.
- Review evidence reads the verdicts the review document defines, so a review
  that approves with non-blocking notes is merge evidence and one that blocks is
  not. The older spelling is still read, so past records stay usable. The
  verdict is read by markup rather than by position: a verdict line inside a
  fenced block, behind a quote marker or in backticks is an example and is never
  read as the record's own, and findings that discuss approval cannot read as
  approval. A record that carries two verdicts disagreeing with each other is
  refused as ambiguous instead of being resolved by guessing which was meant.
- No flag accepts an asserted pass. One would read as a gate while checking
  nothing.
- A review whose verdict changes after a block is resolved states the new
  verdict in place of the old one. Two verdicts left disagreeing in one record
  are refused, because which of them is current cannot be read from the record.

### Legacy of Goku II 16 MiB runtime verification

- The Legacy of Goku II profile declares a 16 MiB generated expansion, so the
  SDK can produce a padded derivative whose first 8 MiB are the canonical image
  byte for byte and whose tail is `0xFF`. The canonical image is never written:
  every experiment runs against an independently copied fixture whose digest is
  recorded before and after.
- A padded derivative was driven through 5,520 emulated frames to an interactive
  overworld, counted from the emulator's own frame callback and driven through
  the emulator's own key API. `KEYINPUT` is read as confirmation only; nothing
  writes to it.
- A controlled derivative demonstrates a genuine guest CPU data read above the
  canonical 8 MiB boundary. A 12-byte read-only object was relocated to
  `0x08800000` and its single pointer literal rewritten; the same instructions,
  at the same program counters, retrieve the same values from the expanded
  region, and the original address stops being read. The read watchpoint channel
  is re-validated against a known boot-path load on every run, and the probe
  reports no result if that validation fails.
- The route is documented end to end in
  [`docs/research/LOGII_16MIB_RUNTIME.md`](docs/research/LOGII_16MIB_RUNTIME.md),
  including what it does not establish: one emulator in two builds, no hardware,
  a single verified expanded address rather than a range, and no claim about
  behaviour above 16 MiB or under any banking scheme.

## 2026-10-31

### Legacy of Goku II authored-image route

- The Legacy of Goku II profile declares a 384-byte free region at `0x007FEA01`,
  so the authored-image route allocates inside that profile's image rather than
  refusing for want of a declared region. The region is the window left between
  two relocation targets once the configured safety margin is taken off both
  ends, and it is zero at a 1,216-byte margin: a change to that margin re-derives
  the number rather than inheriting it.
- Declaring a free region grants no relocation capability. Legacy of Goku II text
  relocation stays refused, because its pointer table aliases - 260 slots reach
  246 distinct targets - and that is unaffected by how much room the image has.
- The route is documented end to end in
  [`docs/research/LOGII_AUTHORED_IMAGE_ROUTE.md`](docs/research/LOGII_AUTHORED_IMAGE_ROUTE.md),
  including what it does not establish: no engine was run against the declared
  region, and no claim is made about a 16 MiB image.

## 2026-10-29

### Map entries

- Added a headless 8x8 screen-entry model: it captures a rectangle of a layer's
  stitched entry plane with its map and layer identity and places it at 8x8 tile
  offsets, including across a 256x256 chunk boundary. Every destination chunk cell
  gets a copy-on-write body composed from that cell's current content with the
  rectangle rewritten and every other entry carried verbatim, so template chunks,
  canonical chunks and untouched cells keep their entries.
- The ordinal vocabulary is the map's assembled character block, not the layer's
  displayed set, so a referenced ordinal the layer never draws can be placed. An
  ordinal past the block, an assembled ordinal with no source tile, and an entry
  with palette-bank bits are refused, the last because no runtime observation of a
  non-zero bank exists. Flip bits are carried verbatim.
- Entry editing reads a cell whose layout value is an authored chunk ordinal, so an
  area the chunk placement model placed is captured and rewritten from the chunk
  that ordinal names rather than from the canonical chunk.
- The build accepts the same rule: an authored chunk body may use any ordinal the
  map's assembled character block backs, a flipped such entry included, and the
  built image carries the placed entry.
- An out-of-plane capture or destination, a shared layer record, a non-editable
  layer, a cross-map or cross-layer destination and an unresolvable authored value
  are each refused with a reason, leaving memory, history and disk unchanged. A
  placement that changes nothing adds no history entry.
- One gesture is one undo entry, undo and redo restore exact entries, and Save
  replaces the existing layout and chunk documents atomically, each on its own:
  Save is not a transaction across documents. An interrupted Save leaves a
  project that still opens, because the authored chunks are written before the
  layout that names them. A reopen reproduces
  the same entries, and two independent runs with the same edits produce
  byte-identical documents. Verified headless only: no emulator run has observed
  an authored entry or a flip bit in the game.

### Map placement

- Added a headless placement model for an editable map layer: it captures a block
  or a rectangle of chunk references, previews and places it within the same map,
  merges a drag stroke into one history entry, and replaces each project document
  atomically on its own, so a Save is not a transaction across documents;
  out-of-grid, read-only, cross-map, shared-record and unknown-chunk placements are
  refused with the SDK's own reason. It is tested without a window; no emulator run
  has observed a stamped rectangle in the game.
- The placement model refuses to open a project whose recorded base image digest
  differs from the digest the caller supplies, and a save reports the placements
  that differ from the saved document, including a placement removed by an undo
  before that save.
- Each project document is replaced atomically on Save, so a Save that fails partway
  can leave an earlier document updated, and the model stays unsaved until the Save
  reports success. A Save that reports success ends an open drag stroke; a Save that
  raises leaves it open.
- A capture reads the in-memory project, so a capture of an edited area copies what
  was placed there rather than the canonical image's blocks at those cells.

### Editor design package

- Added the first actionable design package for the native map editor under
  `docs/product/editor-design/`: one task (capture an existing feature, stamp it
  elsewhere, undo, save) specified input by input, with its capability ceiling
  quoted from the technical audit and eight annotated states drawn as SVG.
- The package records why it does not repeat the two rejected prototypes, and
  separates what is ready to build from what rests on an assumption and what is
  blocked.
- Corrections from the independent verification: a refusal the SDK does not raise
  is gone, the refusal surface and the History rows match the specification, and
  the package text passes the public-surface screen.
- The refused-preview diagram draws only the ghost cells that fit and names the
  two positions outside the layer in its inset, as the specification states.
- Placement contract corrected against the measured image: a 4 x 2 fixture layer
  with its chunk values and differing-position count replaces the impossible one,
  one block is defined as one 256 x 256-pixel chunk placement, the package states
  the chunk-arrangement scope, preview and placement and undo change memory while
  Save is the only write, and the blocking warning states what is unknown.
- The review report records those separately identified corrections beside the
  earlier findings, each marked as a correction rather than a finding.
- The independent review of those corrections is answered: the acceptance assertion
  names destination blocks beside their 0-based project-document cells, the numbering
  rule is stated once in the block definition, placements and undo apply to the
  in-memory project while Save is the only write to disk, and the two capture
  diagrams start at block 1, as the specification's well example does.
- The round two review's wording residue is gone: the drag assumption now assumes the
  in-memory cost of applying one stroke, the F26 resolution applies the batch to the
  in-memory project and re-applies its changes on redo, and the review report records
  both sentences as F36.
- The redo rule now states its invariant: while one layer authority is fixed for an
  editing session, the revalidation cannot fail, and a session that reads the layer
  authority again either starts with an empty history or revalidates every redo.
- The save count now points at the saved point rather than past it: undoing back to a
  save leaves nothing to count and disables Save, while undoing past it leaves the
  project Modified with those placements still to save.

### Continuous integration

- GitHub CI is two workflows instead of one. A pull request update starts a single
  one-job gate that classifies the change, runs the digests and the tests that tier
  selects, and runs the tree-wide quality gates; a superseded run of the same
  branch is cancelled instead of finishing.
- A documentation-only change runs all four tree-wide quality gates, architecture
  and public release included, because their rules read documentation paths.
- A deleted or renamed documentation path selects the broader `premerge` tier; an
  added or modified one stays documentation-only.
- The merge tool refuses a local gate record whose `record.sha256` digest is
  missing, malformed or does not match the record. The digest proves the record
  was not altered after the gate wrote it; it does not prove the record is
  authentic.
- The testing document states that a push to `master` runs the tiered gate only,
  and that a hosted full-suite pass is a manual dispatch.
- The full fourteen-job regression moved to a hand-dispatched workflow. The full
  suite stays mandatory before a merge through `.\scripts\local-ci.ps1` and the
  local-gate record the merge tool requires.
- The full local gate is fail-closed about its own record: it prints `PASS` only
  after `record.txt` exists and its digest was written, and a missing hashing
  cmdlet is a named failure instead of a green line with no record.

## 2026-10-28

### Repository hosting

- Development moved to GitHub: `origin` is `siruiusamory-cmyk/dragonbyte-z`, the
  GitLab remote is read-only history with its push disabled, and the merge tool
  and the workflow docs name pull requests instead of merge requests.
- The public site and the project links point at the GitHub repository.
- The merge tool pins the reviewed commit on GitHub's side, so a branch pushed
  between the review and the merge cannot land unreviewed code.

### Line endings

- The coverage documents are checked out with LF line endings on every platform,
  so a checkout matches what their renderer writes.

## 2026-10-03

### Public progress site

- Redesigned the progress site as a Frutiger Aero desktop. Each section opens
  in its own glass window, a taskbar links to every window, and sidebar
  gadgets show the buildout meter, the per-family tallies, the next phase and
  three headline measurements.
- The capability index and the latest verified wins are forum-style lists whose
  rows expand to show their detail; the roadmap to 1.0 reads as a thread with
  one post per phase.
- New hand-drawn wallpaper and icon set; every figure on the page is still
  derived from the capability registry and the project status data.
- All text meets WCAG AA contrast, interactive targets are at least 24 px tall,
  and the layout stacks into one column on phones without horizontal scrolling.

### Follow-up fixes

- The roadmap now shows Phase 3, graphics and actor authoring, as in progress,
  since graphics import has shipped; the desktop gadget reads "Working on now".
- Keyboard and reading order now follow the window layout, the taskbar no
  longer covers a focused element at the bottom of the screen, and the
  screenshot's caption is attached to its figure.
- On narrow screens the taskbar fades at its edge to show that more windows
  scroll into view.
- The taskbar is built from the site's navigation data, the wallpaper follows
  the configured base path, and a roadmap line marked as shipped without the
  expected separator now stops the build instead of rendering as planned.

### README

- Corrected the current status to the registry's 21 / 24 (88%), with AUTHOR
  4 / 7, and named the next capability after graphics import shipped.
