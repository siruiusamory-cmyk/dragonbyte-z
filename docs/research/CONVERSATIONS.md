# Conversations in Buu's Fury

What the Dialogue tab and `tools/webfoot/conversations.py` rest on. Each claim says
how it was established: **measured** (read from the ROM by a tool in this
repository), **runtime** (observed in mGBA on a ROM built from a private copy), or
**not established**.

## How a conversation is stored

- The event table holds 522 pointers. Each names an array of record pointers that
  ends on a word whose high half is zero; the low half is the entry the next talk
  starts from. *Measured; ending on 0 and on 2 both runtime.*
- A record is `u16 next, u8 kind, u8 argument`, then its payload. Kind 5 is a spoken
  page: portrait in the argument, a text handle at +4. Kind 6 is a spoken page with
  values filled in. Kinds 0 and 4 are scripts; kind 7 is a jump. *Measured.*
- A handle is a container selector, a start and a length. The container table has
  64 slots; the game ships seven containers in selectors 0 to 6. The table is named
  by one literal. *Measured.* Selectors 7 to 63 read correctly through both the
  kind-5 and the kind-6 reader once the table is copied and the literal repointed.
  *Runtime, 57 of 57 through the first reader and 56 of 56 through the second.*
- Among the pages a conversation can reach there are 2,244 kind-5 records naming
  2,181 distinct handles, and no two handles overlap. *Measured.*

## What the writer does

- The seven base-game containers are never rewritten. A reworded line is stored in
  an authored container, and the handle word of every record that carried the old
  handle is rewritten. *Measured by test: base containers byte-identical, only handle
  words, the table literal and assigned NPC words differ inside the base image.*
- An authored conversation is new records and a new pointer array in expanded ROM
  space. An NPC is given it by the conversation word of its map record.
- Builds are deterministic: the same project builds the same bytes. *Measured.*

## Presentation

- A window holds four lines of 144 pixels with a portrait, or two lines of 128
  pixels in the small box. Unit 0x0A breaks a line and 0x0B a window. A leading `!`,
  `@` or `#` puts the box at the top, middle or bottom and is not drawn.
  *Measured from the layout routine; wrap and paging runtime.*
- Portrait values 8 to 162 are Library portraits. Portrait 0 shows no face, centres
  the words and uses the low box. *Runtime.*
- The preview draws glyphs, wrapping and paging. It does not draw the frame, its
  colours or its screen position. *Not established as pixel-exact.*

## Flags

- Native 27 tests a save flag, 28 tests it inverted, 29 sets it. A flag rule is two
  small scripts placed before and after the pages. *Runtime: the flag byte changed
  and the second conversation was said on the next talk.*
- Free numbers come from a census of every script the conversation records carry,
  plain and packed, and the event scripts: 157 to 186, 216 to 222 and 224 to 233 are named by
  none. *Measured.*
- Two base-game scripts set a flag whose number is computed while playing. Which
  numbers they reach is **not established**.

## Kept as they are

- Kind-6 pages. Their container loading is proven, but how the filled-in values
  constrain the text is not, so the editor shows them and does not change them.
- Script steps, jumps, portraits and page order of a base-game conversation.
- Branching to another conversation is done by placing that conversation's pages in
  the same array. No jump record is authored.
