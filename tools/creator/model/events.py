"""The event editor's model: events, their steps, the story's flags, and undo.

An event the creator made is ``evt-N``. Every edit is written to the project at
once through the SDK's validated documents, and undo and redo restore those
documents as they were. A flag keeps its number for good, so a save file made
with an earlier build still means the same thing.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from tools.dragonbyte.session import Session
from tools.webfoot import conversations as cv
from tools.webfoot import events as ev
from tools.webfoot import map_authoring as new_maps
from tools.webfoot import map_objects as mo
from tools.webfoot import map_view
from tools.webfoot import story_flags as sf

from .project import CreatorError

TALK, REGION, NOT_PROVEN, gate, trace_script = ev.TALK, ev.REGION, ev.NOT_PROVEN, ev.gate, ev.trace_script
MAP_PIXELS, PLAYER = ev.MAP_PIXELS, ev.PLAYER

TRIGGERS = {
    ev.TALK: "Talk to a character",
    ev.ENTER: "Enter a map",
    ev.LEAVE: "Leave a map",
    ev.REGION: "Walk into a region",
}
ACTIVATIONS = {
    "walk_in": "each time the player walks in",
    "once": "the first time the player walks in, each visit to the map",
    "press_a": "when the player presses A inside it",
}
FILES = (ev.EVENTS_FILE, sf.FLAGS_FILE, cv.CONVERSATIONS_FILE, mo.OBJECTS_FILE)
OPENS, CLOSES = ("if", "together"), ("end_if", "end_together")
NATIVE_NAMES = {24: "read the player's answer", 27: "test a flag", 28: "test a flag is not set",
                29: "set a flag", 30: "clear a flag", 35: "play music", 43: "open a passage",
                44: "close a passage", 56: "start steps at the same time",
                58: "wait for steps that started together", 60: "play a gesture",
                83: "make a character face a way",
                96: "walk a character", 97: "walk a character at a speed", 136: "wait",
                139: "look at the map's regions again",
                146: "count an item", 147: "give an item", 148: "take an item",
                178: "show a banner", 181: "start another conversation"}


@dataclass(frozen=True)
class Action:
    """One kind of step in the library, and whether the running game was seen to do it."""

    kind: str
    group: str
    title: str
    about: str
    template: tuple
    proven: bool


def _action(kind, group, title, about, template) -> Action:
    return Action(kind, group, title, about, template, ev.gate(template) in ev.PROVEN)


LIBRARY = (
    _action("say", "Dialogue", "Say", "A character says a page of dialogue.", ("say", 0, "Hello.")),
    _action("ask", "Dialogue", "Ask", "A page that ends in two choices the player picks from.",
            ("ask", 0, "Will you help?", "Yes", "No")),
    _action("if answer", "Dialogue", "If the answer is", "Do the steps inside when the player "
            "picked that choice in the last Ask.", ("if", "answer", 1)),
    _action("walk", "Characters", "Walk to", "A character walks to a point on the map.",
            ("walk", ev.PLAYER, 0, 0)),
    _action("face", "Characters", "Face", "A character turns to face a direction.",
            ("face", ev.PLAYER, "down")),
    _action("face toward", "Characters", "Face toward", "A character turns to face another "
            "one standing on the same map.", ("face toward", ev.PLAYER, ev.PLAYER)),
    _action("wait", "Characters", "Wait", "Wait before the next step, counted in frames.",
            ("wait", 60)),
    _action("together", "Characters", "Do together", "Walk and face several characters at "
            "the same time.", ("together",)),
    _action("lie down", "Characters", "Lie down", "The player lies down and stays down "
            "until a Stand up step.", ("lie down",)),
    _action("stand up", "Characters", "Stand up", "The player stands up after lying down.",
            ("stand up",)),
    _action("if flag", "Story flags", "If flag is set", "Do the steps inside when the story "
            "remembers this flag.", ("if", "flag", "")),
    _action("if not_flag", "Story flags", "If flag is not set", "Do the steps inside when the "
            "story does not remember this flag.", ("if", "not_flag", "")),
    _action("set", "Story flags", "Set flag", "Remember this flag. It is kept in the save file.",
            ("set", "")),
    _action("clear", "Story flags", "Clear flag", "Forget this flag.", ("clear", "")),
    _action("if item", "Items", "If the player has", "Do the steps inside when the player "
            "holds at least this many of a piece of gear.", ("if", "item", 1, 1)),
    _action("give", "Items", "Give item", "Give the player one piece of gear. It is listed "
            "under Equip in the game's menu. Supplies cannot be given yet.", ("give", 1)),
    _action("take", "Items", "Take item", "Take one piece of gear away from the player.",
            ("take", 1)),
    _action("open", "World", "Open passage", "Make a rectangle of the map walkable.",
            ("open", 0, 0, 8, 8)),
    _action("close", "World", "Close passage", "Block a rectangle of the map.",
            ("close", 0, 0, 8, 8)),
    _action("music", "World", "Play music", "Change the music.", ("music", 0)),
    _action("else", "Flow", "Else", "The steps after this run when the If above was not true.",
            ("else",)),
    _action("end_if", "Flow", "End If", "Closes the If above.", ("end_if",)),
    _action("end", "Flow", "End", "Stop the event here.", ("end",)),
)


@dataclass(frozen=True)
class Row:
    key: str
    title: str
    trigger: str
    group: str
    where: str
    problem: str


@dataclass(frozen=True)
class StepRow:
    index: int
    depth: int
    text: str
    problem: str
    step: tuple


@dataclass(frozen=True)
class FlagRow:
    """One line of the Story view."""

    name: str
    number: int
    set_by: tuple
    read_by: tuple
    note: str


def _friendly(exc: Exception) -> str:
    text = str(exc).strip()
    return text[:1].upper() + text[1:] if text else "That change could not be made."


class EventStudio:
    def __init__(self, project_dir: Path, rom_path: Path) -> None:
        self.directory = Path(project_dir)
        self.image = Path(rom_path).read_bytes()
        session = Session()
        session.open_rom(Path(rom_path))
        self.profile = session.profile
        self.font = cv.Font(self.image, self.profile)
        self._labels = map_view.read_map_index(self.image, self.profile)
        self._undo: list[tuple] = []
        self._redo: list[tuple] = []
        self._sizes: dict = {}
        self._game = None

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def _snapshot(self) -> dict:
        return {name: (self.directory / name).read_bytes() if (self.directory / name).is_file()
                else None for name in FILES}

    def _restore(self, snapshot: dict) -> None:
        for name, data in snapshot.items():
            path = self.directory / name
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)

    def _edit(self, action) -> None:
        before = self._snapshot()
        try:
            action()
        except CreatorError:
            self._restore(before)
            raise
        except (ValueError, OSError, IndexError) as exc:
            self._restore(before)
            raise CreatorError(_friendly(exc)) from exc
        after = self._snapshot()
        changed = [name for name in FILES if before[name] != after[name]]
        if changed:
            self._undo.append(({name: before[name] for name in changed},
                               {name: after[name] for name in changed}))
            self._redo.clear()

    def _step_back(self, here: list, there: list, was: int, now: int) -> None:
        """Move one edit between undo and redo, touching only the files it changed.

        A file another tab changed since is left alone and the move is refused,
        so an edit made in Maps or Dialogue is never thrown away from here.
        """
        if not here:
            return
        current = self._snapshot()
        if any(current[name] != data for name, data in here[-1][was].items()):
            raise CreatorError(
                "Something this step changed was changed again in another tab. Undo "
                "that change there first.")
        self._restore(here[-1][now])
        there.append(here.pop())

    def undo(self) -> None:
        self._step_back(self._undo, self._redo, 1, 0)

    def redo(self) -> None:
        self._step_back(self._redo, self._undo, 0, 1)

    def document(self) -> dict:
        try:
            return ev.read_document(self.directory)
        except ValueError as exc:
            raise CreatorError(_friendly(exc)) from exc

    def registry(self) -> sf.Flags:
        try:
            return sf.read_flags(self.directory)
        except ValueError as exc:
            raise CreatorError(_friendly(exc)) from exc

    def _objects(self) -> dict:
        try:
            return mo.read_document(self.directory)
        except ValueError:
            return {}

    def _talks(self) -> dict:
        try:
            return dict(cv.read_document(self.directory).talks)
        except ValueError:
            return {}

    def event(self, key: str) -> ev.Event:
        event = self.document().get(key)
        if event is None:
            raise CreatorError("That event is gone.")
        return event

    def map_title(self, identity: str) -> str:
        if identity.startswith("map-new:"):
            return identity[8:]
        if identity.startswith("map:") and int(identity[4:]) < len(self._labels):
            return f"{int(identity[4:]):03d} {self._labels[int(identity[4:])].name or 'Unnamed map'}"
        return identity or "no map"

    def maps(self) -> list[tuple[str, str]]:
        """Every map an event can belong to: the creator's own first, then the game's."""
        own = [(f"map-new:{item.name}", f"★ {item.name}")
               for item in new_maps.authored_maps(self.directory).ordered()]
        return own + [(f"map:{entry.index:04d}", self.map_title(f"map:{entry.index:04d}"))
                      for entry in self._labels]

    def where(self, key: str, event: ev.Event) -> str:
        if event.trigger == ev.TALK:
            users = self.users(key)
            return "said by " + ", ".join(users[:2]) if users else "no character says it yet"
        return f"{TRIGGERS.get(event.trigger, event.trigger).lower()}: {self.map_title(event.map)}"

    def rows(self) -> list[Row]:
        problems = dict(reversed(self.problems()))
        return [Row(key, event.name or "Unnamed event", event.trigger, event.group,
                    self.where(key, event), problems.get(key, ""))
                for key, event in sorted(self.document().items(),
                                         key=lambda pair: ev.event_order(pair[0]))]

    def users(self, key: str) -> list[str]:
        """Every character that says this event, as 'map: character'."""
        found = []
        for identity, item in sorted(self._objects().items()):
            found += [f"{self.map_title(identity)}: game character {slot}"
                      for slot, reference in item.says.items() if reference == key]
            found += [f"{self.map_title(identity)}: {made.name or name}"
                      for name, made in item.made.items() if made.says == key]
        return found

    def _donors(self) -> dict:
        return {item.name: item.donor
                for item in new_maps.authored_maps(self.directory).ordered()}

    def _cast_rows(self):
        """Each map the event runs on as the build leaves its object array."""
        return ev.cast(self.image, self.profile, self._objects(), self._donors())

    def _size(self, place: str) -> tuple[int, int]:
        """One map's pixel extent, read once and kept for the session."""
        if place not in self._sizes:
            self._sizes[place] = ev.map_pixels(self.image, self.profile, place, self._donors())
        return self._sizes[place]

    def _context(self, document=None) -> tuple:
        """The places, cast and map sizes the step checks need for one pass over the events."""
        objects = self._objects()
        return (ev.places(document or self.document(), objects),
                ev.cast(self.image, self.profile, objects, self._donors()), self._size)

    def characters(self, key: str) -> list[tuple[str, str]]:
        """The characters this event can name, the player first, as (identity, name)."""
        event = self.event(key)
        objects = self._objects()
        places = ev.places({key: event}, objects)[key]
        rows = [(ev.PLAYER, "Player")]
        try:
            rows_of = self._cast_rows()
            for place in places:
                made = objects[place].made if place in objects else {}
                for placed in rows_of(place):
                    if not placed.character:
                        continue
                    name = (made[placed.key[5:]].name or placed.key[5:]
                            if placed.key.startswith("made:") else
                            f"game character {placed.key[5:]}")
                    rows.append((f"{place}/{placed.key}", name))
        except (ValueError, OSError):
            return rows[:1]
        return rows

    def _write(self, events: dict) -> None:
        self._edit(lambda: ev.write_document(self.directory, events))

    def _next_key(self) -> str:
        taken = [ev.event_order(key) for key in self.document()] + [
            ev.event_order(reference) for item in self._objects().values()
            for reference in [*item.says.values(), *(made.says for made in item.made.values())]
            if ev.EVENT_ID.fullmatch(reference)]
        return f"evt-{max(taken, default=0) + 1}"

    def new_event(self, name: str, trigger: str = ev.TALK, map: str = "", rect=(),
                  activation: str = "") -> str:
        key = self._next_key()
        first = ("say", 0, "Hello.") if trigger == ev.TALK else ("end",)
        event = ev.Event(" ".join(name.split())[:40] or "New event", "", trigger, map,
                         tuple(rect), activation, (first,))
        self._check_trigger(event)
        self._write({**self.document(), key: event})
        return key

    def duplicate(self, key: str) -> str:
        event = self.event(key)
        new = self._next_key()
        copy = replace(event, name=(event.name + " copy")[:40])
        if event.trigger in (ev.ENTER, ev.LEAVE):
            copy = replace(copy, trigger=ev.TALK, map="")
        self._write({**self.document(), new: copy})
        return new

    def _change(self, key: str, change) -> None:
        event = self.event(key)
        self._write({**self.document(), key: change(event)})

    def rename(self, key: str, name: str) -> None:
        self._change(key, lambda event: replace(event, name=" ".join(name.split())[:40]))

    def set_group(self, key: str, group: str) -> None:
        self._change(key, lambda event: replace(event, group=" ".join(group.split())[:40]))

    def delete(self, key: str) -> None:
        self.event(key)
        users = self.users(key)
        if users:
            raise CreatorError(
                "This event is still said by " + "; ".join(users[:6])
                + ". Give them another conversation first.")
        self._write({other: event for other, event in self.document().items() if other != key})

    def _check_trigger(self, event: ev.Event) -> None:
        if event.trigger not in TRIGGERS:
            raise CreatorError("Choose how the event starts.")
        if event.trigger not in ev.PROVEN:
            raise CreatorError(f"Starting an event this way {ev.NOT_PROVEN}.")
        if event.trigger == ev.TALK:
            return
        if not event.map:
            raise CreatorError("Choose the map this event belongs to.")
        if event.trigger == ev.REGION:
            if event.activation not in ACTIVATIONS:
                raise CreatorError("Choose how the region is set off.")
            if len(event.rect) != 4 or event.rect[0] >= event.rect[2] or (
                    event.rect[1] >= event.rect[3]) or min(event.rect) < 0:
                raise CreatorError("Draw the region as a rectangle on the map.")
        other = next((name for name, held in self.document().items()
                      if held is not event and event.trigger in (ev.ENTER, ev.LEAVE)
                      and (held.trigger, held.map) == (event.trigger, event.map)), None)
        if other is not None:
            raise CreatorError(
                f"The event {self.document()[other].name or other!r} already runs then. A "
                "map has one event for entering and one for leaving.")

    def set_trigger(self, key: str, trigger: str, map: str = "", rect=(),
                    activation: str = "") -> None:
        current = self.event(key)
        if trigger != ev.TALK and self.users(key):
            raise CreatorError("A character says this event. Give them another conversation first.")
        changed = replace(current, trigger=trigger, map="" if trigger == ev.TALK else map,
                          rect=tuple(rect) if trigger == ev.REGION else (),
                          activation=activation if trigger == ev.REGION else "")
        events = {**self.document(), key: changed}

        def action() -> None:
            ev.write_document(self.directory, {other: held for other, held in events.items()
                                               if other != key})
            self._check_trigger(changed)
            ev.write_document(self.directory, events)

        self._edit(action)

    def regions(self, identity: str) -> list[tuple[str, str, tuple]]:
        """The authored regions on one map: event id, name and rectangle."""
        return [(key, event.name, event.rect) for key, event in self.document().items()
                if event.trigger == ev.REGION and event.map == identity and len(event.rect) == 4]

    def flag_names(self) -> list[str]:
        return sorted(self.registry().names)

    def describe(self, step: tuple, key: str = "", names: dict | None = None) -> str:
        kind, values = step[0], step[1:]
        names = dict(names or {})

        def who(identity: str) -> str:
            return names.get(identity) or ev.character_name(identity)

        if kind in ev.CHARACTER_STEPS and key and not names:
            try:
                names.update(self.characters(key))
            except CreatorError:
                pass
        try:
            if kind in ("say", "ask"):
                text = " / ".join(str(values[1]).split("\n"))
                tail = f"   [{values[2]}] [{values[3]}]" if kind == "ask" else ""
                return f"{'Ask' if kind == 'ask' else 'Say'}   \"{text[:70]}\"{tail}"
            if kind == "if":
                form = values[0]
                if form == "flag":
                    return f"If flag [{values[1] or 'choose a flag'}] is set"
                if form == "not_flag":
                    return f"If flag [{values[1] or 'choose a flag'}] is not set"
                if form == "item":
                    return f"If the player has at least {values[2]} of item {values[1]}"
                return f"If the answer is choice {values[1]}"
            if kind in ("set", "clear"):
                return f"{'Set' if kind == 'set' else 'Clear'} flag   [{values[0] or 'choose a flag'}]"
            if kind in ("give", "take"):
                return f"{'Give' if kind == 'give' else 'Take'} item   {values[0]}"
            if kind in ("open", "close"):
                return (f"{'Open' if kind == 'open' else 'Close'} passage   "
                        f"({values[0]}, {values[1]}) to ({values[2]}, {values[3]})")
            if kind == "music":
                return f"Play music   {values[0]}"
            if kind == "walk":
                speed = f" at speed {values[3]}" if len(values) == 4 else ""
                return f"{who(values[0])} walks to {values[1]}, {values[2]}{speed}"
            if kind == "face":
                return f"{who(values[0])} faces {values[1]}"
            if kind == "face toward":
                return f"{who(values[0])} turns to face {who(values[1])}"
            if kind == "wait":
                return f"Wait   {values[0]} frames"
        except IndexError:
            pass
        return {"else": "Else", "end_if": "End If", "end": "End", "together": "Do together",
                "end_together": "End together", "lie down": "Lie down",
                "stand up": "Stand up"}.get(kind, f"Unknown step {kind!r}")

    def step_problem(self, key: str, step: tuple, index: int = -1, places=None,
                     cast_rows=None, size_of=None) -> str:
        event = self.event(key)
        if places is None:
            places, cast_rows, size_of = self._context()
            places = places.get(key, ())
        problem = ev.step_problem(step, self.registry().names, event.trigger,
                                  ev.as_conversation(event), places, cast_rows, size_of)
        if not problem and step[0] in ("say", "ask"):
            try:
                problem = cv.page_problem(self.font, ev.spoken(step), step[1])
            except ValueError as exc:
                problem = _friendly(exc)
        if not problem and step[0] == "face toward" and index >= 0:
            try:
                ev.face_direction(event.steps, index, cast_rows, ev.label(key, event))
            except (ev.EventError, ValueError) as exc:
                problem = _friendly(exc)
        return problem

    def steps(self, key: str, context=None) -> list[StepRow]:
        places, cast_rows, size_of = context or self._context()
        used = places.get(key, ())
        rows, depth = [], 0
        characters = dict(self.characters(key))
        for index, step in enumerate(self.event(key).steps):
            if step[0] in ("else",) + CLOSES:
                depth = max(depth - 1, 0)
            rows.append(StepRow(index, depth, self.describe(step, key, characters),
                                self.step_problem(key, step, index, used, cast_rows, size_of),
                                step))
            if step[0] in ("else",) + OPENS:
                depth += 1
        left = ev.lying_witness(self.event(key).steps)
        if 0 <= left < len(rows):
            rows[left] = replace(rows[left], problem=ev.LEFT_LYING)
        return rows

    def _steps_at(self, key: str, index: int) -> list:
        steps = list(self.event(key).steps)
        if not 0 <= index < len(steps):
            raise CreatorError("Choose a step first.")
        return steps

    def _set_steps(self, key: str, steps) -> None:
        self._change(key, lambda event: replace(event, steps=tuple(tuple(s) for s in steps)))

    def add_step(self, key: str, step: tuple, at: int = -1) -> int:
        """Add a step; an If or a Do together arrives with its end, so the list nests."""
        steps = list(self.event(key).steps)
        at = len(steps) if at < 0 else min(at, len(steps))
        ends = {"if": ("end_if",), "together": ("end_together",)}
        steps[at:at] = [tuple(step)] + ([ends[step[0]]] if step[0] in ends else [])
        self._set_steps(key, steps)
        return at

    def set_step(self, key: str, index: int, step: tuple) -> None:
        steps = self._steps_at(key, index)
        problem = self.step_problem(key, tuple(step))
        if problem and steps[index][0] != step[0]:
            raise CreatorError(problem)
        steps[index] = tuple(step)
        self._set_steps(key, steps)

    def _block(self, steps: list, index: int) -> int:
        """The index just past the step, or past the whole block it opens."""
        if steps[index][0] not in OPENS:
            return index + 1
        depth = 0
        for at in range(index, len(steps)):
            depth += (steps[at][0] in OPENS) - (steps[at][0] in CLOSES)
            if depth == 0:
                return at + 1
        return len(steps)

    def remove_step(self, key: str, index: int) -> None:
        """Remove a step. An If or a Do together goes with everything inside it."""
        steps = self._steps_at(key, index)
        if steps[index][0] in CLOSES:
            raise CreatorError("Remove the If or Do together this belongs to; its end goes "
                               "with it.")
        del steps[index:self._block(steps, index)]
        self._set_steps(key, steps)

    def move_step(self, key: str, index: int, move: int) -> int:
        """Move a step, or a whole If or Do together block, one place up or down."""
        steps = self._steps_at(key, index)
        if steps[index][0] in ("else",) + CLOSES:
            raise CreatorError("Move the If or Do together this belongs to instead.")
        end = self._block(steps, index)
        block = steps[index:end]
        rest = steps[:index] + steps[end:]
        to = index + move
        if not 0 <= to <= len(rest):
            raise CreatorError("That step cannot move further.")
        rest[to:to] = block
        self._set_steps(key, rest)
        return to

    def add_flag(self, name: str) -> str:
        name = name.strip()
        self._edit(lambda: sf.write_flags(
            self.directory, sf.assign(self.registry(), name, self.profile)))
        return name

    def _uses(self) -> dict[str, tuple[list, list]]:
        """For each flag name, who sets it and who reads it."""
        uses: dict[str, tuple[list, list]] = {}

        def note(name: str, side: int, who: str) -> None:
            if name:
                found = uses.setdefault(name, ([], []))[side]
                if who not in found:
                    found.append(who)

        for key, event in self.document().items():
            who = f"event {event.name or key}"
            for step in event.steps:
                if step[0] in ("set", "clear") and len(step) > 1:
                    note(step[1], 0, who)
                if step[0] == "if" and len(step) > 2 and step[1] in ("flag", "not_flag"):
                    note(step[2], 1, who)
        for key, talk in self._talks().items():
            note(talk.sets, 0, f"conversation {talk.name or key}")
            note(talk.when, 1, f"conversation {talk.name or key}")
        for identity, item in self._objects().items():
            for slot, rule in item.appears.items():
                note(rule.removeprefix("!"), 1,
                     f"{self.map_title(identity)}: game character {slot} appears")
            for name, made in item.made.items():
                if made.appears and made.appears != "always":
                    note(made.appears.removeprefix("!"), 1,
                         f"{self.map_title(identity)}: {made.name or name} appears")
        return uses

    def story(self) -> list[FlagRow]:
        """The Story view: every flag, who sets it, who reads it, and what looks wrong."""
        uses = self._uses()
        rows = []
        for name, number in sorted(self.registry().names.items()):
            set_by, read_by = uses.get(name, ([], []))
            note = ("Nothing uses this flag." if not set_by and not read_by
                    else "Nothing sets this flag, so what reads it never changes." if not set_by
                    else "Nothing reads this flag." if not read_by else "")
            rows.append(FlagRow(name, number, tuple(set_by), tuple(read_by), note))
        return rows

    def rename_flag(self, old: str, new: str) -> None:
        """Rename a flag everywhere it is used; its number, and so every save, is kept."""
        new = new.strip()

        def swap(name: str) -> str:
            return new if name == old else name

        def action() -> None:
            registry = sf.renamed(self.registry(), old, new)
            events = {
                key: replace(event, steps=tuple(
                    tuple(new if item == old and (
                        (at == 1 and step[0] in ("set", "clear"))
                        or (at == 2 and step[:2] in (("if", "flag"), ("if", "not_flag"))))
                          else item for at, item in enumerate(step)) for step in event.steps))
                for key, event in ev.read_document(self.directory).items()}
            talks = cv.read_document(self.directory)
            objects = {identity: replace(
                item,
                appears={slot: ("!" if rule.startswith("!") else "") + swap(rule.removeprefix("!"))
                         for slot, rule in item.appears.items()},
                made={name: replace(made, appears=("!" if made.appears.startswith("!") else "")
                                    + swap(made.appears.removeprefix("!")))
                      for name, made in item.made.items()})
                for identity, item in mo.read_document(self.directory).items()}
            legacy = self.directory / cv.CONVERSATIONS_FILE
            if legacy.is_file():
                cv.write_document(self.directory, cv.Document(
                    talks.lines, {key: replace(talk, sets=swap(talk.sets), when=swap(talk.when))
                                  for key, talk in talks.talks.items()}, {}))
            sf.write_flags(self.directory, registry)
            ev.write_document(self.directory, events)
            if objects:
                mo.write_document(self.directory, objects)

        self._edit(action)

    def delete_flag(self, name: str) -> None:
        """Retire a flag nothing uses. Its number is never given to another flag."""
        set_by, read_by = self._uses().get(name, ([], []))
        if set_by or read_by:
            raise CreatorError(
                f"The flag {name!r} is still used by " + "; ".join((set_by + read_by)[:6]) + ".")
        self._edit(lambda: sf.write_flags(self.directory, sf.retired(self.registry(), name)))

    def problems(self) -> list[tuple[str, str]]:
        """Everything a build would refuse or a player could never reach, by event."""
        found: list[tuple[str, str]] = []
        document = self.document()
        flags = self.registry().names
        context = self._context(document)
        places, cast_rows, size_of = context
        owners: dict[tuple, str] = {}
        for key, event in sorted(document.items(), key=lambda pair: ev.event_order(pair[0])):
            where = ev.label(key, event)
            try:
                ev.tree(event, flags, where, ev.as_conversation(event),
                        places.get(key, ()), cast_rows, size_of)
                for row in self.steps(key, context):
                    if row.problem:
                        raise ev.EventError(f"{where}, step {row.index + 1}: {row.problem}")
            except ValueError as exc:
                found.append((key, _friendly(exc)))
            if event.trigger == ev.TALK and not self.users(key):
                found.append((key, f"{_friendly(where)}: no character says it, so it never runs. "
                                   "Give it to a character in Maps."))
            if event.trigger in (ev.ENTER, ev.LEAVE):
                other = owners.setdefault((event.trigger, event.map), key)
                if other != key:
                    found.append((key, f"{_friendly(where)}: {ev.label(other, document[other])} "
                                       "already runs then on the same map."))
            if event.trigger != ev.TALK and not (
                    ev._CANONICAL.fullmatch(event.map) or ev._AUTHORED.fullmatch(event.map)):
                found.append((key, f"{_friendly(where)}: it belongs to no map."))
        for identity, item in self._objects().items():
            for reference in [*item.says.values(), *(made.says for made in item.made.values())]:
                if ev.EVENT_ID.fullmatch(reference) and reference not in document:
                    found.append(("", f"{self.map_title(identity)}: a character says the event "
                                      f"{reference!r}, which is gone."))
                elif reference in document and document[reference].trigger != ev.TALK:
                    found.append((reference, f"{self.map_title(identity)}: a character says "
                                             "an event that does not start by talking."))
        for row in self.story():
            if row.read_by and not row.set_by:
                found.append(("", f"Flag {row.name!r}: {row.note}"))
        for name in sorted(set(self._uses()) - set(flags)):
            found.append(("", f"The flag {name!r} is used but is not in the story's flags."))
        return found

    def trace(self, output: Path) -> list[str]:
        """What the running game executed, in order, in the creator's own words."""
        document = self.document()
        lines = []
        for item in ev.read_trace(output):
            if item[0] == "flag":
                lines.append(f"flag [{item[1]}] is {'set' if item[2] else 'not set'}")
                continue
            event = document.get(item[1])
            if event is None or item[2] >= len(event.steps):
                lines.append(f"ran: {item[1]}, step {item[2] + 1} (the project changed since "
                             "this build)")
            else:
                lines.append(f"ran: {event.name or item[1]}, step {item[2] + 1}: "
                             f"{self.describe(event.steps[item[2]], item[1])}")
        return lines

    def game_events(self) -> list[tuple[str, str]]:
        """The base game's own conversations, to look at. They are never changed here."""
        if self._game is None:
            self._game = cv.read_conversations(self.image, self.profile)
        rows = []
        for event, item in self._game.items():
            first = next((cv.decode(entry.text).replace("\n", " ")[:50] for entry in item.entries
                          if entry.text is not None), "no speech")
            rows.append((f"event:{event:04d}", f"{event:04d}  {first}"))
        return rows

    def game_steps(self, reference: str) -> list[tuple[str, bool]]:
        """A base-game conversation as steps; a step not understood is shown and kept."""
        self.game_events()
        spec = ev.OPCODE_SETS[ev.CONTRACTS[self.profile.id]["encoding"]]
        rows: list[tuple[str, bool]] = []
        for index, entry in enumerate(self._game[int(reference[6:])].entries):
            head = f"{index + 1}  "
            if entry.kind == cv.SPEECH and entry.text is not None:
                rows.append((head + f"Say   \"{cv.decode(entry.text)[:70]}\"", True))
            elif entry.kind == cv.SCRIPT:
                natives, at, reach = [], entry.record + 3, 0
                try:
                    for _ in range(400):
                        instruction = ev.decode_instruction(self.image, at, spec)
                        name = spec.lookup(instruction.opcode).name
                        if name == "native_stack":
                            natives.append(instruction.operands[0].value)
                        reach = max(reach, instruction.target or 0)
                        if name == "terminate" and at >= reach:
                            break
                        at += instruction.encoded_length
                except (ValueError, IndexError):
                    pass
                known = [NATIVE_NAMES[slot] for slot in natives if slot in NATIVE_NAMES]
                unknown = [slot for slot in natives if slot not in NATIVE_NAMES and slot > 11]
                if unknown:
                    rows.append((head + "Game step not yet understood (native "
                                 + ", ".join(map(str, unknown[:8])) + ")", False))
                else:
                    rows.append((head + "Script: " + (", ".join(known) or "picks the next step"),
                                 True))
            else:
                rows.append((head + f"Game step not yet understood (record kind {entry.kind})",
                             False))
        return rows
