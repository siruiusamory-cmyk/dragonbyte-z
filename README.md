<p align="center">
  <img src="docs/banner.png" alt="Postboy Advance banner" width="900">
</p>

<!-- TODO demo GIF: short screen recording of New Project, one text edit, Build, Play. Needs an owner-approved capture (docs/decisions/0006-public-product-screenshots.md). Add as docs/demo.gif then replace this comment with the image. -->
<!-- TODO social preview asset: export docs/social-preview.png (1280x640) from the banner and set it in GitHub: Settings > General > Social preview. -->
# Postboy Advance

**Make your own game on the Dragon Ball Z: Buu's Fury engine. No programming, no hex editing.**

![License](https://img.shields.io/badge/license-MPL--2.0-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%2010%20%2F%2011-blueviolet.svg)
![Editors](https://img.shields.io/badge/editors-6-lightgrey.svg)

Postboy Advance was formerly called DragonByte Z.

Postboy Advance is a free Windows program for changing the Game Boy Advance game
*Dragon Ball Z: Buu's Fury*. You open your own copy of the game, change its text,
maps, characters, conversations, story events and enemies by pointing and typing,
press **Build**, and play the result in an emulator.

No ROM or game data is included. You supply your own legally obtained copy of the
game. The program only ever reads it and writes your version to a new file.

## Contents

- [What you need](#what-you-need)
- [Windows quick start](#windows-quick-start)
- [What you can edit](#what-you-can-edit)
- [Sharing what you make](#sharing-what-you-make)
- [Supported games and maturity](#supported-games-and-maturity)
- [Project status](#project-status)
- [Limits and ROM ownership](#limits-and-rom-ownership)
- [Getting help](#getting-help)
- [For developers and ROM hackers](#for-developers-and-rom-hackers)
- [License](#license)

## What you need

- A PC with Windows 10 or 11.
- Your own ROM file of **Dragon Ball Z: Buu's Fury (USA)**. A ROM is a copy of a
  game cartridge saved as a `.gba` file. The program tells you whether the file you
  picked is the right one.
- [mGBA](https://mgba.io/), a free emulator, to play what you build.

You do not need Python, a terminal or any programming tools.

## Windows quick start

1. Open the [latest release](https://github.com/siruiusamory-cmyk/postboy-advance/releases/latest)
   and download the `.zip` file under **Assets**.
2. Right-click the downloaded file, choose **Extract All**, and pick a folder you
   can find again. Keep everything in that folder together.
3. Double-click **`Postboy Advance.exe`**. The program is not code-signed, so Windows
   may show "Windows protected your PC". Choose **More info**, then **Run anyway**.
4. Choose **New Project**, pick your ROM, and give the project a name.
5. Change something. The **Text** tab is the easiest place to start: pick a line,
   type your own words under "Your text".
6. Press **F6** to build, then **F5** to play your version in mGBA.

Release v0.9.0.dev0 and earlier were published under the old name, DragonByte Z,
so in those downloads the program is `DragonByte Z.exe`.

The [user guide](docs/creator.md) walks through every tab with the same steps and
says what to do when something goes wrong.

Building from the source code instead is covered in [INSTALL.md](INSTALL.md).

## What you can edit

Each tab in the program edits one part of the game.

### Text

Reword menus, item names and other on-screen text. Text the game cannot store is
refused as you type, with the reason shown under the box.

### Library

Browse every map, character sprite and portrait in the game with a picture and a
search box, and give them your own names. From here you can repaint a sprite pixel
by pixel, change its colours, and make one new character of your own by drawing it
or importing a PNG picture.

### Maps

Make a new map from one of the game's maps and change it by pointing: place pieces,
draw tiles, resize it, paint where the player can walk, and add or remove doors
between maps. Move, copy, restyle and remove the characters standing on a map.

### Dialogue

Reword what characters say and write new conversations with pages and portraits. A
preview wraps and pages the words the way the game does.

### Events

Build what happens from steps, with no scripting. Talking to a character, entering
a map or walking into an area can show lines, ask a two-way question, remember the
answer, give or take gear, open a passage, and make characters walk and turn.

### Enemies

Make your own enemy types by copying one of the game's and changing its hit points,
experience, strength and endurance. Place them on maps and choose when they appear.

### Safety nets

- Every change can be undone with **Ctrl+Z**.
- Unsaved work survives a crash and is offered back the next time you open the project.
- A build that fails keeps your last working build.
- Your original ROM is never changed.

## Sharing what you make

Share a **patch**, never the game itself. A patch is a small `.bps` file holding
only your changes; other people apply it to their own copy of the game. The built
`.gba` file contains the whole commercial game and must not be uploaded or sent to
anyone. [Release artefacts](docs/release-artefacts.md) explains how to export a patch.

## Supported games and maturity

| Game | What works today |
| --- | --- |
| **Dragon Ball Z: Buu's Fury (USA)** | Everything described above. This is the game the program is built for. |
| **Dragon Ball Z: The Legacy of Goku II** | Developer tools only: a few command-line edits. Not available in the program. |
| **Dragon Ball Z: The Legacy of Goku** | Developer tools only: the game is recognised and its scripts can be read. Not available in the program. |

Only the exact supported version of each game is accepted. A file with the right
title but different contents is refused. [ROM profiles](docs/rom-profiles.md) lists
the accepted versions.

## Project status

**Early release, still changing.** The program works from start to finish for the
tabs above, but it is not finished and project files may change format before
version 1.0. Keep backups of your project folder.

Not possible yet: supplies and shops, battles, and music.
[Limits of this version](docs/creator.md#limits-of-this-version) has the full list.

The long-term goal is to rebuild the first *Legacy of Goku* as new content inside
the Buu's Fury engine. That is a later milestone, it is not delivered, and it is
not a standalone remake: it will always need your own copy of the original games.

## Limits and ROM ownership

- This project does not contain, link to or help you find any ROM.
- Do not publish ROMs, built games, pictures taken out of the game, save files or
  save states. Share patches only.
- Your original ROM stays read-only. Every build is written to a new file inside
  your project's `build` folder.
- This is a fan project. It is not affiliated with or endorsed by the owners of
  Dragon Ball Z or the publishers of these games.

The full rules are in the [ROM safety contract](docs/ROM_SAFETY.md).

## Getting help

- Something went wrong: see
  [If something goes wrong](docs/creator.md#if-something-goes-wrong) in the user guide.
- Found a bug or want a feature: open an
  [issue](https://github.com/siruiusamory-cmyk/postboy-advance/issues). Say what you
  did, what you expected and what happened. Never attach a ROM, save file or
  anything taken out of the game.

## For developers and ROM hackers

Under the program sits the **Webfoot SDK**: a command-line toolkit and a set of
measured format documents for all three Webfoot Dragon Ball Z games on the Game Boy
Advance.

- [SDK overview](docs/sdk-overview.md): what the command line can edit, per game.
- [Install from source](INSTALL.md) and [contributing](CONTRIBUTING.md).
- [Documentation index](docs/README.md): formats, architecture and research.
- [Development policy](docs/DEVELOPMENT.md) and
  [measured project state](docs/PROJECT_STATE.md).

Sister projects reconstruct each game's code:
[Legacy of Goku](https://github.com/siruiusamory-cmyk/legacyofgoku-disasm),
[Legacy of Goku II](https://github.com/siruiusamory-cmyk/legacyofgoku2-disasm) and
[Buu's Fury](https://github.com/siruiusamory-cmyk/buusfury-disasm).

## License

The original code here is released under the [Mozilla Public License 2.0](LICENSE).
Third-party material keeps its own terms, listed in the
[third-party notices](THIRD-PARTY-NOTICES.md). No commercial game content is
supplied or relicensed.

This project was renamed from DragonByte Z to avoid confusion with
[DragonByteZ](https://github.com/spicybung/DragonByteZ) by spicybung, an independent
project under the MIT License. The part of this project that unpacks the games'
compressed data follows that project's code, including some fixed numbers carried
over from it, as the third-party notices describe. Postboy Advance is not affiliated
with DragonByteZ.
