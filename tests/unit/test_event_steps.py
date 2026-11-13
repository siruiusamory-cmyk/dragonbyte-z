"""Character steps: the actor commands the running game was seen to perform.

Nothing here reads a ROM. The cast is stated by the test, so what is under test is
the instruction list each step compiles to and every refusal beside it. The
reference a built map gives is asserted by the ROM-gated test in
``tests/integration/test_events_rom.py``.
"""

from __future__ import annotations

import pytest

from tools.webfoot import events as ev
from tools.webfoot import map_objects as mo
from tools.webfoot.data.placement_contracts import CONTRACTS
from tools.webfoot.data.script_specs import OPCODE_SETS
from tools.webfoot.map_render import canonical_profile

PROFILE = canonical_profile()
SPEC = OPCODE_SETS[CONTRACTS[PROFILE.id]["encoding"]]
FLAGS = {"quest": 7}
MAP = "map:0033"
ELSEWHERE = "map:0102"
ROWS = {
    MAP: (mo.Placed("game:0", 8, 8, False),
          mo.Placed("game:1", 100, 100, True),
          mo.Placed("made:elder-1", 200, 100, True)),
    ELSEWHERE: (mo.Placed("game:1", 40, 40, True),),
}
SIZES = {MAP: (1280, 512), ELSEWHERE: (256, 256)}


def cast(place):
    return ROWS.get(place, ())


def size_of(place):
    return SIZES[place]


def plan(steps, rows=cast, places=(), sizes=None):
    event = ev.Event("Scene", steps=tuple(steps))
    return ev.compile_conversation("evt-1", event, FLAGS, PROFILE,
                                   lambda raw, portrait: "", rows, places, sizes).plan


def scripts(steps, rows=cast, places=(), sizes=None):
    """The instruction list of each script record the event builds to."""
    return [list(payload) for kind, payload, _target, _step in plan(steps, rows, places, sizes)
            if kind == "script"]


def records_of(steps) -> list[bytes]:
    compiled = ev.compile_conversation("evt-1", ev.Event("Scene", steps=tuple(steps)),
                                       FLAGS, PROFILE, lambda raw, portrait: "", cast)
    return compiled.records([0] * len(compiled.pages))


def instructions(data: bytes) -> list[tuple[int, list[int]]]:
    """Every instruction of one script record, decoded from the bytes built for it."""
    found, at = [], 3
    for _ in range(64):
        instruction = ev.decode_instruction(data, at, SPEC)
        found.append((instruction.opcode, [item.value for item in instruction.operands]))
        at += instruction.encoded_length
        if instruction.opcode == 17:
            return found
    raise AssertionError("the built record never terminates")


def test_walk_pushes_the_character_then_the_point_then_native_96():
    assert scripts([("walk", ev.PLAYER, 200, 152)]) == [
        ["push_many 3 0 200 152", "native_stack 96"]]
    assert scripts([("walk", f"{MAP}/game:1", 200, 152)]) == [
        ["push_many 3 -2 200 152", "native_stack 96"]]


def test_a_walk_with_a_speed_is_native_97_with_the_speed_last():
    for speed in (50, 100, 200):
        assert scripts([("walk", f"{MAP}/made:elder-1", 200, 152, speed)]) == [
            [f"push_many 4 -3 200 152 {speed}", "native_stack 97"]]


def test_face_is_native_83_with_the_four_directions_numbered():
    for name, number in (("down", 0), ("up", 1), ("left", 2), ("right", 3)):
        assert scripts([("face", f"{MAP}/game:1", name)]) == [
            [f"push_many 2 -2 {number}", "native_stack 83"]]
        assert scripts([("face", ev.PLAYER, name)]) == [
            [f"push_many 2 0 {number}", "native_stack 83"]]


def test_wait_is_native_136_for_one_to_two_hundred_and_fifty_five_frames():
    assert scripts([("wait", 1)]) == [["push_byte 1", "native_stack 136"]]
    assert scripts([("wait", 255)]) == [["push_byte 255", "native_stack 136"]]


def test_together_is_one_record_that_opens_with_56_and_closes_with_58():
    steps = [("together",), ("walk", ev.PLAYER, 200, 152),
             ("face", f"{MAP}/game:1", "left"), ("end_together",)]
    assert scripts(steps) == [[
        "native_stack 56", "push_many 3 0 200 152", "native_stack 96",
        "push_many 2 -2 2", "native_stack 83", "native_stack 58"]]
    assert [step for _kind, _payload, _target, step in plan(steps)] == [0]


def test_face_toward_turns_on_the_larger_axis_and_sideways_on_a_tie():
    target = f"{MAP}/game:1"
    sides = {(0, 100): 3, (200, 100): 2, (100, 0): 0, (100, 200): 1, (0, 0): 3}
    for (x, y), facing in sides.items():
        assert scripts([("walk", ev.PLAYER, x, y), ("face toward", ev.PLAYER, target)])[1] == [
            f"push_many 2 0 {facing}", "native_stack 83"]


def test_face_toward_uses_where_an_earlier_walk_left_the_character():
    mover = f"{MAP}/game:1"
    steps = [("walk", mover, 20, 100), ("face toward", f"{MAP}/made:elder-1", mover)]
    assert scripts(steps)[1] == ["push_many 2 -3 2", "native_stack 83"]


def test_face_toward_after_a_walk_inside_an_if_is_refused():
    steps = [("if", "flag", "quest"), ("walk", ev.PLAYER, 10, 10), ("end_if",),
             ("face toward", ev.PLAYER, f"{MAP}/game:1")]
    with pytest.raises(ev.EventError, match="choose Face and a direction"):
        plan(steps)


def test_face_toward_without_a_known_place_is_refused():
    with pytest.raises(ev.EventError, match="choose Face and a direction"):
        plan([("face toward", ev.PLAYER, f"{MAP}/game:1")])
    with pytest.raises(ev.EventError, match="stand on different maps"):
        plan([("face toward", f"{MAP}/game:1", f"{ELSEWHERE}/game:1")])


def test_each_character_step_is_its_own_record():
    records = records_of([("walk", ev.PLAYER, 200, 152), ("wait", 30)])
    assert instructions(records[0]) == [(29, [3, 0, 200, 152]), (2, [96]), (17, [])]
    assert instructions(records[1]) == [(0, [30]), (2, [136]), (17, [])]


def test_the_built_together_record_carries_the_bracket():
    data = records_of([("together",), ("walk", ev.PLAYER, 200, 152),
                       ("face", f"{MAP}/game:1", "left"), ("end_together",)])[0]
    assert instructions(data) == [(2, [56]), (29, [3, 0, 200, 152]), (2, [96]),
                                  (29, [2, -2, 2]), (2, [83]), (2, [58]), (17, [])]


def test_a_walk_outside_the_map_is_refused():
    problem = ev.step_problem(("walk", ev.PLAYER, -1, 0), FLAGS)
    assert problem == "A character walks to a point on the map, in whole pixels."
    assert ev.step_problem(("walk", ev.PLAYER, 0, 0), FLAGS, places=(MAP,),
                           size_of=size_of) == ""


def test_a_walk_target_past_the_maps_edge_is_refused():
    assert scripts([("walk", ev.PLAYER, 1279, 511)], places=(MAP,), sizes=size_of) == [
        ["push_many 3 0 1279 511", "native_stack 96"]]
    message = ("A walk stays on the map: map:0033 is 1280 pixels across and 512 down, so "
               "across is 0 to 1279 and down is 0 to 511.")
    for x, y in ((1280, 511), (1279, 512), (4000, 4000)):
        assert ev.step_problem(("walk", ev.PLAYER, x, y), FLAGS, places=(MAP,),
                               size_of=size_of) == message
    with pytest.raises(ev.EventError, match="A walk stays on the map"):
        plan([("walk", ev.PLAYER, 1280, 0)], places=(MAP,), sizes=size_of)


def test_a_speed_that_was_not_measured_is_refused():
    for speed in (0, 25, 75, 150, 401):
        assert ev.step_problem(("walk", ev.PLAYER, 0, 0, speed), FLAGS) == (
            "A walk speed is Slow (50), Normal (100) or Fast (200).")


def test_a_face_needs_one_of_the_four_directions():
    problem = ev.step_problem(("face", ev.PLAYER, "sideways"), FLAGS)
    assert problem == "A character faces down, up, left or right."


def test_a_wait_outside_one_to_two_hundred_and_fifty_five_frames_is_refused():
    for frames in (0, 256, 600):
        assert ev.step_problem(("wait", frames), FLAGS) == (
            "A wait is 1 to 255 frames; a longer pause is two Wait steps.")


def test_a_together_needs_two_steps_and_holds_only_walks_and_faces():
    with pytest.raises(ev.EventError, match="at least two steps"):
        plan([("together",), ("walk", ev.PLAYER, 0, 0), ("end_together",)])
    with pytest.raises(ev.EventError, match="only Walk to and Face"):
        plan([("together",), ("walk", ev.PLAYER, 0, 0), ("wait", 10), ("end_together",)])


def test_a_together_inside_a_together_is_refused():
    with pytest.raises(ev.EventError, match="cannot hold another Do together"):
        plan([("together",), ("walk", ev.PLAYER, 0, 0), ("together",),
              ("face", ev.PLAYER, "down"), ("end_together",), ("end_together",)])


def test_a_together_that_is_never_closed_is_refused():
    with pytest.raises(ev.EventError, match="never closed"):
        plan([("together",), ("walk", ev.PLAYER, 0, 0), ("face", ev.PLAYER, "down")])


def test_a_character_step_on_a_map_load_is_refused():
    for trigger in (ev.ENTER, ev.LEAVE):
        problem = ev.step_problem(("walk", ev.PLAYER, 0, 0), FLAGS, trigger, False)
        assert problem.startswith("A character step runs only in a conversation")
    event = ev.Event("Gate", trigger=ev.ENTER, map=MAP, steps=(("walk", ev.PLAYER, 0, 0),))
    with pytest.raises(ev.EventError, match="only in a conversation"):
        ev.compile_script("evt-2", event, FLAGS, PROFILE)


def test_a_character_step_in_a_region_that_says_nothing_is_refused():
    event = ev.Event("Wire", trigger=ev.REGION, map=MAP, rect=(0, 0, 8, 8),
                     activation="walk_in", steps=(("walk", ev.PLAYER, 0, 0),))
    with pytest.raises(ev.EventError, match="only in a conversation"):
        ev.compile_script("evt-3", event, FLAGS, PROFILE)


def test_lie_down_and_stand_up_are_native_60_on_the_player():
    assert scripts([("lie down",), ("stand up",)]) == [
        ["push_byte 0", "push_byte 16", "native_stack 60"],
        ["push_byte 0", "push_byte 0", "native_stack 60"]]
    assert instructions(records_of([("lie down",), ("stand up",)])[0]) == [
        (0, [0]), (0, [16]), (2, [60]), (17, [])]


def test_a_lie_down_with_no_later_stand_up_on_a_path_is_refused():
    for steps in ((("lie down",),),
                  (("say", 0, "Hi."), ("lie down",), ("wait", 5)),
                  (("if", "flag", "quest"), ("lie down",), ("end_if",)),
                  (("lie down",), ("if", "flag", "quest"), ("stand up",), ("end_if",)),
                  (("if", "flag", "quest"), ("lie down",), ("else",), ("stand up",),
                   ("end_if",)),
                  (("lie down",), ("if", "flag", "quest"), ("end",), ("end_if",),
                   ("stand up",))):
        with pytest.raises(ev.EventError, match="left lying down"):
            plan(steps)


def test_a_lie_down_the_player_is_stood_up_from_on_every_path_builds():
    for steps in ((("lie down",), ("stand up",)),
                  (("stand up",), ("lie down",), ("stand up",)),
                  (("lie down",), ("if", "flag", "quest"), ("wait", 5), ("end_if",),
                   ("stand up",)),
                  (("lie down",), ("if", "flag", "quest"), ("stand up",), ("else",),
                   ("stand up",), ("end_if",))):
        assert scripts(steps)[-1] == ["push_byte 0", "push_byte 0", "native_stack 60"]


def test_the_refusal_names_the_step_that_leaves_the_player_down():
    with pytest.raises(ev.EventError,
                       match=r"step 2: The player would be left lying down"):
        plan([("say", 0, "Hi."), ("lie down",), ("wait", 5)])
    assert ev.lying_witness((("lie down",), ("wait", 5))) == 0
    assert ev.lying_witness((("lie down",), ("stand up",), ("lie down",))) == 2
    assert ev.lying_witness((("stand up",), ("lie down",), ("stand up",))) == -1


def test_a_face_direction_outside_the_four_cannot_reach_the_compiler():
    for bad in ("sideways", "Down", "", 5, -1):
        with pytest.raises(ev.EventError):
            plan([("face", ev.PLAYER, bad)])
    assert "down, up, left or right" in ev.step_problem(("face", ev.PLAYER, "sideways"), FLAGS)


def test_a_hand_edited_face_direction_is_refused_when_the_document_is_built(tmp_path):
    ev.write_document(tmp_path, {"evt-1": ev.Event(
        "Scene", steps=(("say", 0, "Hi."), ("face", ev.PLAYER, "sideways")))})
    loaded = ev.read_document(tmp_path)["evt-1"]
    with pytest.raises(ev.EventError, match="down, up, left or right"):
        ev.compile_conversation("evt-1", loaded, FLAGS, PROFILE,
                                lambda raw, portrait: "", cast)


def test_a_reference_to_something_that_is_not_a_character_is_refused():
    with pytest.raises(ev.EventError, match="game character 0 of map:0033"):
        plan([("walk", f"{MAP}/game:0", 0, 0)])
    with pytest.raises(ev.EventError, match="game character 9 of map:0033"):
        plan([("walk", f"{MAP}/game:9", 0, 0)])


def test_a_character_step_cannot_name_a_character_of_another_map():
    elsewhere = f"{ELSEWHERE}/game:1"
    message = ("game character 1 of map:0102 stands on map:0102, but this event runs on "
               "map:0033; a character step can only name a character of every map the "
               "event runs on.")
    for step in (("walk", elsewhere, 0, 0), ("face", elsewhere, "down"),
                 ("face toward", ev.PLAYER, elsewhere)):
        assert ev.step_problem(step, FLAGS, places=(MAP,), cast_rows=cast) == message
    with pytest.raises(ev.EventError, match="stands on map:0102"):
        plan([("walk", elsewhere, 0, 0)], places=(MAP,))
    assert ev.step_problem(("face", f"{MAP}/game:1", "down"), FLAGS, places=(MAP,),
                           cast_rows=cast) == ""
    assert ev.step_problem(("face", ev.PLAYER, "down"), FLAGS, places=(ELSEWHERE,),
                           cast_rows=cast) == ""


def test_a_character_step_said_on_two_maps_must_fit_both():
    message = ev.step_problem(("face", f"{MAP}/game:1", "down"), FLAGS,
                              places=(MAP, ELSEWHERE), cast_rows=cast)
    assert "map:0033, map:0102" in message
    with pytest.raises(ev.EventError, match="map:0033, map:0102"):
        plan([("walk", f"{MAP}/game:1", 0, 0)], places=(MAP, ELSEWHERE))


def test_a_character_step_naming_nobody_is_shown_as_a_problem():
    missing = f"{MAP}/made:nobody"
    assert ev.step_problem(("walk", missing, 0, 0), FLAGS, places=(MAP,),
                           cast_rows=cast) == (
        "nobody of map:0033 is not a character in this project's build of that map")
    with pytest.raises(ev.EventError, match="nobody of map:0033 is not a character"):
        plan([("walk", missing, 0, 0)], places=(MAP,))


def test_the_reference_counts_the_array_position_not_the_characters():
    assert scripts([("face", ev.PLAYER, "down")]) == [["push_many 2 0 0", "native_stack 83"]]
    assert scripts([("face", f"{MAP}/game:1", "down")]) == [
        ["push_many 2 -2 0", "native_stack 83"]]
    assert scripts([("face", f"{MAP}/made:elder-1", "down")]) == [
        ["push_many 2 -3 0", "native_stack 83"]]
