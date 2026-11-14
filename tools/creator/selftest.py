"""The whole authoring loop, driven through the real window and reported as JSON.

It calls the same slots the toolbar calls, on the real window, with a real ROM,
and saves a screenshot at every step. It runs identically from source and from
the packaged executable, which is what proves the package carries everything.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest

from tools.webfoot import enemy_types, map_objects as mo, story_flags

from .model.project import RECOVERY_FILE, CreatorProject

RECORD = "text:0010"
JOB_TIMEOUT_MS = 120_000


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _wait_for_job(window) -> dict:
    loop = QEventLoop()
    outcome: dict = {}
    connection = window.job_finished.connect(
        lambda _action, result: (outcome.update(result), loop.quit())
    )
    QTimer.singleShot(JOB_TIMEOUT_MS, loop.quit)
    loop.exec()
    window.job_finished.disconnect(connection)
    return outcome


def run_selftest(app, window, options) -> int:
    workdir = Path(options.workdir)
    shots = workdir / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    steps: list[dict] = []
    rom_before = _sha256(options.rom)

    def step(name: str, passed: bool, detail: str = "") -> None:
        app.processEvents()
        shot = shots / f"{len(steps) + 1:02d}-{name}.png"
        window.grab().save(str(shot))
        steps.append({"step": name, "passed": bool(passed), "detail": detail, "screenshot": shot.name})

    def edit(text: str) -> bool:
        window.editor.select(RECORD)
        window.editor.editor.setPlainText(text)
        return window.editor.apply_pending()

    step("launch", window.isVisible() and window.project is None)
    directory = workdir / "Self Test"
    step("new-project", window.create_project(options.rom, directory, "Self Test"), str(directory))
    project = window.project
    original = project.record(RECORD).original

    step("edit-text", edit("DBZ Test") and project.dirty, f"{original!r} -> 'DBZ Test'")
    window.undo()
    undone = project.record(RECORD).text == original
    window.redo()
    step("undo-redo", undone and project.record(RECORD).text == "DBZ Test")
    saved = window.save() and 'text = "DBZ Test"' in (directory / "text" / "strings.toml").read_text(encoding="utf-8")
    step("save", saved and not project.dirty)

    window.editor.editor.setFocus()
    QTest.keyClicks(window.editor.editor, "Go ")
    typed = window.editor.apply_pending() and project.record(RECORD).text == "Go DBZ Test"
    QTest.keySequence(window.editor.editor, QKeySequence(QKeySequence.StandardKey.Undo))
    QTest.keySequence(window.editor.editor, QKeySequence(QKeySequence.StandardKey.Redo))
    QTest.keySequence(window.editor.editor, QKeySequence(QKeySequence.StandardKey.Redo))
    QTest.keySequence(window.editor.editor, QKeySequence(QKeySequence.StandardKey.Undo))
    step(
        "keyboard-type-and-undo",
        typed
        and project.record(RECORD).text == "DBZ Test"
        and not project.dirty
        and not window.messages,
        project.record(RECORD).text,
    )

    window.build()
    first = _wait_for_job(window)
    step("build", bool(first.get("ok")) and project.build_status() == "current", json.dumps(first))

    played = True
    if options.play_seconds:
        window.play()
        deadline = time.monotonic() + options.play_seconds
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.05)
        emulator = window.emulator_process
        played = emulator is not None and emulator.poll() is None
        step("play", played, f"emulator pid {getattr(emulator, 'pid', None)}")
        if emulator is not None:
            emulator.terminate()

    edit("DBZ Test 2")
    step("edit-again", project.build_status() == "outdated")
    window.build()
    second = _wait_for_job(window)
    step(
        "rebuild",
        bool(second.get("ok")) and second.get("sha256") != first.get("sha256"),
        json.dumps(second),
    )

    edit("{broken")
    step("validation-feedback", "control code" in window.editor.feedback.text(), window.editor.feedback.text())
    edit("Unsaved after a crash")
    recovery = (directory / RECOVERY_FILE).is_file()
    reopened = CreatorProject.open(directory)
    step("recovery-file", recovery and reopened.recovered.get(RECORD) == "Unsaved after a crash")

    library = window.library
    window.tabs.setCurrentWidget(library)

    def pictured(key: str) -> bool:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            app.processEvents()
            if library.select(key) and not library.picture.pixmap().isNull():
                return True
            time.sleep(0.1)
        return False

    def visible() -> list[str]:
        rows = (library.items.item(row) for row in range(library.items.count()))
        return [item.text() for item in rows if not item.isHidden()]

    seen = pictured("sprite:0002")
    library.name.setText("My Hero")
    library.apply_name()
    library.search.setText("my hero")
    step(
        "library-sprite-named",
        seen and len(visible()) == 1 and "Maps that place it: map:0046." in library.uses.text(),
        library.uses.text(),
    )
    step("library-portrait", pictured("portrait:008") and bool(library.uses.text()), library.uses.text())
    library.select("map:0451")
    library.name.setText("Far Place")
    library._poll()
    kept = library.name.text() == "Far Place"
    library.kinds.setCurrentIndex(1)
    step("library-typed-name-kept", kept and '"map:0451": "Far Place"' in (directory / "library" / "names.json").read_text(encoding="utf-8"))
    seen = pictured("map:0019")
    library.search.setText("map:0019")
    step("library-map", seen and len(visible()) == 1, library.status.text())
    maps = window.maps
    studio = maps.studio
    window.tabs.setCurrentWidget(maps)
    retail = "map:0033"

    def drag(points, right: bool = False) -> None:
        maps.down(*points[0], right)
        for point in points[1:]:
            maps.move(*point)
        maps.up(*points[-1])

    def new_map(name: str) -> str:
        maps.select_map(retail)
        maps.pick_name = lambda _title, _text: name
        maps.new_map()
        return maps.key

    def door(source: str, box, destination: str, arrival) -> None:
        maps.select_map(source)
        maps.set_tool("doors")
        maps.pick_destination = lambda: destination
        drag([box[:2], box[2:]])
        maps.down(*arrival)

    def layer(slot: int):
        return next(item for item in studio.layers(maps.key) if item.slot == slot)

    arena = new_map("arena")
    maps.layer_box.setCurrentIndex(maps.layer_box.findData(0))
    maps.set_tool("pieces")
    maps.pieces.setCurrentRow(2)
    placed = maps.pieces.currentItem().data(0x0100)
    drag([(10, 10)])
    step("map-new-and-place", arena == "map-new:arena" and layer(0).cells[0] == placed, arena)

    maps.layer_box.setCurrentIndex(maps.layer_box.findData(0))
    maps.set_tool("tiles")
    target = studio.tile_at(arena, 0, 1, 2, 2)
    source = next((row, column) for row in range(32) for column in range(32)
                  if studio.tile_at(arena, 0, 1, row, column) != target)
    drag([(256 + source[1] * 8 + 2, source[0] * 8 + 2)], right=True)
    drag([(256 + 18, 18), (256 + 26, 18)])
    step("map-tiles", isinstance(layer(0).cells[1], str) and studio.tile_at(arena, 0, 1, 2, 2) == maps.tile)

    maps.layer_box.setCurrentIndex(maps.layer_box.findData(2))
    maps.resize_layer(5, 2)
    step("map-resize", layer(2).columns == 5 and layer(2).rows == 2)

    maps.set_tool("walls")
    maps.block.setChecked(True)
    drag([(250, y) for y in range(0, 2048, 8)])
    maps.open.setChecked(True)
    for y in range(112, 224, 8):
        drag([(x, y) for x in range(80, 248, 8)])
    walls = studio.collision(arena)
    step(
        "map-walls",
        not walls[20 * 32 + 3] >> 7 & 1 and bool(walls[14 * 32 + 2] >> 4 & 1)
        and studio.collision(retail) != walls,
    )

    ring = new_map("ring")
    door(retail, (296, 152, 312, 216), arena, (144, 160))
    door(arena, (200, 184, 216, 224), ring, (144, 160))
    door(ring, (320, 152, 336, 216), retail, (200, 160))
    for key in (arena, ring):
        maps.select_map(key)
        maps.door_list.setCurrentRow(0)
        maps.toggle_door()
    inside = studio.doors(arena)
    step(
        "map-doors",
        [item.removed for item in inside] == [True, False] and "ring" in inside[1].destination
        and len(studio.doors(retail)) == 2,
        "; ".join(item.destination for item in inside),
    )

    window.undo()
    undone = [item.removed for item in studio.doors(ring)][0] is False
    window.redo()
    step("map-undo-redo", undone and [item.removed for item in studio.doors(ring)][0] is True)

    renamed = new_map("spare")
    maps.pick_name = lambda _title, _text: "extra"
    maps.rename_map()
    step(
        "map-rename-keeps-doors",
        maps.key == "map-new:extra" and renamed == "map-new:spare"
        and "ring" in studio.doors(arena)[1].destination,
    )

    town = "map:0102"
    maps.select_map(town)
    maps.set_tool("characters")
    before = studio.characters(town)
    walker = next(item for item in before if item.box)
    drag([(walker.x, walker.y - 2), (walker.x + 24, walker.y + 14)])
    maps.duplicate_character()
    maps.pick_name = lambda _title, _text: "Twin"
    maps.rename_character()
    maps.pick_look = lambda: before[0].sprite
    maps.change_look()
    maps.choice_list.setCurrentRow(0)
    maps.add_character()
    maps.choose_character(before[-1].key)
    maps.toggle_character()
    window.undo()
    put_back = not studio.characters(town)[len(before) - 1].removed
    window.redo()
    after = studio.characters(town)
    moved = next(item for item in after if item.key == walker.key)
    twin = next((item for item in after if item.name == "Twin"), None)
    maps.select_map(arena)
    maps.choice_list.setCurrentRow(1)
    maps.add_character()
    step(
        "map-characters",
        (moved.x, moved.y) == (walker.x + 24, walker.y + 16) and len(after) == len(before) + 2
        and twin is not None and twin.sprite == before[0].sprite and twin.box != walker.box
        and put_back and after[len(before) - 1].removed
        and len(studio.characters(arena)) == len(studio.characters(retail)) + 1
        and bool(maps.character_note.text()),
        "; ".join(f"{item.key} {item.kind} at {item.x},{item.y}" for item in after if item.made),
    )

    talks = window.dialogue
    window.tabs.setCurrentWidget(talks)
    talks.pick_name = lambda _title, _text: "Greeting"
    talks.new_talk()
    greeting = talks.key
    wrote = talks.set_text("Hello.\nThis was written in DragonByte Z.{page}And this follows.")
    talks.add_page()
    wrote = wrote and talks.set_text("#Goodbye.")
    refused = not talks.set_text("A {zz} code the game does not have.")
    talks.refresh()
    talks.sets.setText("met_greeter")
    talks.apply_rule()
    game_row = next(row.key for row in talks.studio.rows() if not row.mine
                    and any(page.editable for page in talks.studio.pages(row.key)))
    spoken = next(page for page in talks.studio.pages(game_row) if page.editable)
    talks.select(game_row, spoken.index)
    reworded = talks.set_text(spoken.original + " Indeed.")
    window.undo()
    back = talks.studio.pages(game_row)[spoken.index].text == spoken.original
    window.redo()
    window.tabs.setCurrentWidget(maps)
    maps.select_map(town)
    maps.choose_character(twin.key if twin else walker.key)
    maps.pick_talk = lambda: greeting
    maps.choose_talk()
    checks = {
        "wrote": wrote, "refused": refused, "reworded": reworded, "undone": back,
        "pages": len(talks.studio.pages(greeting)) == 2,
        "rule": talks.studio.rule(greeting)[0] == "met_greeter",
        "used": bool(talks.studio.users(greeting)),
        "kept": talks.studio.pages(game_row)[spoken.index].changed,
        "shown": "Greeting" in maps.says_label.text(),
        "preview": len(talks.preview.windows) >= 1,
    }
    step("dialogue", all(checks.values()),
         talks.studio.capacity() + " " + " ".join(name for name, held in checks.items() if not held))

    events = window.events
    window.tabs.setCurrentWidget(events)
    events.pick_name = lambda _title, _text: "Gift"
    events.new_event()
    gift = events.key
    for kind in ("ask", "if answer", "give", "set"):
        events.add_step(kind)
    events._inputs[0][2].setEditText("got_gift")
    flagged = events.apply_step()
    events.add_step("music")
    locked = "not" in events.problem.text() and len(events.studio.event(gift).steps) == 6
    window.undo()
    fewer = events.studio.event(gift).steps[4] == ("set", "")
    window.redo()
    events.show_game.setChecked(True)
    events.select(next(key for key, title in events.studio.game_events()
                       if "no speech" not in title))
    viewed = events.steps.count() > 0 and not events.apply_button.isEnabled()
    events.select(gift)
    window.tabs.setCurrentWidget(maps)
    maps.select_map(town)
    giver = next(item for item in studio.characters(town) if item.made and item.name != "Twin")
    maps.choose_character(giver.key)
    maps.pick_talk = lambda: gift
    maps.choose_talk()
    if twin:
        maps.choose_character(twin.key)
        maps.pick_appears = lambda: "got_gift"
        maps.choose_appears()
    maps.set_tool("regions")
    maps.pick_region = lambda choices: choices[0][0]
    maps.pick_name = lambda _title, _text: "Tripwire"
    drag([(40, 40), (72, 64)])
    window.tabs.setCurrentWidget(events)
    story = {row.name: row for row in events.studio.story()}
    checks = {
        "flagged": flagged, "locked": locked, "undone": fewer, "viewed": viewed,
        "steps": [row.depth for row in events.studio.steps(gift)] == [0, 0, 0, 1, 1, 0],
        "said": bool(events.studio.users(gift)),
        "region": [rect for _key, _name, rect in events.studio.regions(town)] == [(40, 40, 73, 65)],
        "story": "got_gift" in story and bool(story["got_gift"].set_by)
        and bool(story["got_gift"].read_by),
        "clean": not [text for key, text in events.studio.problems() if key == gift],
    }
    events.select(gift)
    events.add_step("walk")
    who = events._inputs[0][2]
    who.setCurrentIndex(max(who.findData(f"{town}/{giver.key}"), 0))
    events._inputs[1][2].setValue(200)
    events._inputs[2][2].setValue(152)
    walked = events.apply_step()
    events.add_step("face")
    events.add_step("wait")
    events.add_step("lie down")
    events.add_step("stand up")
    added = events.studio.event(gift).steps
    checks["character"] = (walked and added[1] == ("walk", f"{town}/{giver.key}", 200, 152)
                           and [step[0] for step in added[2:6]] == ["face", "wait", "lie down",
                                                                    "stand up"]
                           and not [text for key, text in events.studio.problems() if key == gift])
    step("events", all(checks.values()),
         " ".join(name for name, held in checks.items() if not held)
         + " " + "; ".join(text for _key, text in events.studio.problems()))

    enemies = window.enemies
    window.tabs.setCurrentWidget(enemies)
    enemies.pick_donor = lambda rows: next(row.key for row in rows if row.uses)
    enemies.pick_name = lambda _title, _text: "cave wolf"
    enemies.new_enemy()
    beast = enemies.key
    enemies._inputs["hp"].setValue(900)
    edited = enemies.apply()
    made = next((row for row in enemies.studio.project() if row.key == beast), None)
    window.tabs.setCurrentWidget(window.maps)

    window.build()
    built = _wait_for_job(window)
    step("map-build", bool(built.get("ok")) and project.build_status() == "current", json.dumps(built))
    image = project.output.read_bytes()
    written = all(image[at:at + len(record)] == record
                  for at, record in enemies.studio.written_records())
    window.tabs.setCurrentWidget(enemies)
    step("enemies", edited and written and made is not None and made.hp == 900,
         f"{beast}; {len(enemies.studio.project())} type(s); {made.hp if made else 0} HP")

    window.tabs.setCurrentWidget(window.maps)
    maps.select_map("map:0033")
    maps.refresh()
    maps.set_tool("enemies")
    picked = next(row for row in range(maps.enemy_choice_list.count())
                  if maps.enemy_choice_list.item(row).data(Qt.ItemDataRole.UserRole) == beast)
    maps.enemy_choice_list.setCurrentRow(picked)
    maps.down(176, 152)
    maps.up(176, 152)
    maps.enemy_list.setCurrentRow(0)
    maps.enemy_appears.setCurrentIndex(maps.enemy_appears.findData("got_gift"))
    placed_key = maps.chosen_enemy
    placed = [item for item in maps.studio.enemy_placements("map:0033")
              if item.key == placed_key]
    window.build()
    placed_build = _wait_for_job(window)
    built_image = project.output.read_bytes()
    added = [item for item in mo.read_objects(built_image, studio.profile, 33)
             if item.family == mo.PLACEMENT and item.record_offset >= len(studio.image)]
    at = added[0].record_offset if added else 0
    word = int.from_bytes(built_image[at + mo.CONDITION_OFFSET:at + mo.CONDITION_OFFSET + 4],
                          "little") if added else 0
    row = int.from_bytes(built_image[at + mo.TYPE_OFFSET:at + mo.TYPE_OFFSET + 4],
                         "little") if added else -1
    claim = enemy_types.read_types(project.directory, studio.profile, studio.image)
    flag = story_flags.read_flags(project.directory).names.get("got_gift", 0)
    placed_checks = {
        "built": bool(placed_build.get("ok")),
        "one": len(added) == 1,
        "place": bool(added) and (added[0].x, added[0].y) == (176, 152),
        "type": row == claim.entries[beast].row,
        "appears": word == (1 << 16) | flag,
        "count": maps.studio.built_objects("map:0033") == 13,
        "listed": [item.name for item in placed] == [beast.split(":", 1)[1]],
    }
    step("map-enemies", all(placed_checks.values()),
         " ".join(name for name, held in placed_checks.items() if not held)
         + f" {placed_key} at 176, 152; object count "
         f"{maps.studio.enemy_count('map:0033')}/{maps.studio.built_objects('map:0033')}")
    window.tabs.setCurrentWidget(window.editor)

    step("source-rom-unchanged", _sha256(options.rom) == rom_before, rom_before)
    report = {
        "title": window.windowTitle(),
        "passed": all(item["passed"] for item in steps),
        "steps": steps,
        "messages": window.messages,
        "output": str(project.output),
    }
    Path(options.selftest).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    window.project.discard_recovery()
    window.project = None
    window.close()
    return 0 if report["passed"] else 1
