"""The DRAGONBYTE-FINE-001 route driver's step machine, run without an emulator.

There is no Lua interpreter on this host and the repository ships none for tests,
so the driver's schedule is parsed out of the Lua source and its machine is
mirrored in Python here. The model reads the same eight declared steps, applies
the same end conditions and the same two failure rules, and runs them against a
scripted engine. It is a MODEL of the Lua machine, not the Lua machine: the Lua
runs only under the reviewed launcher in stage 2.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "tools/runtime/fine001_route_driver.lua"
FIELDS = ("want_map", "want_vofs", "expect", "hold", "mask", "budget")
EXPECTED_STEPS = [
    "start_map40", "leave_to_39", "release_in_39", "step_east",
    "return_to_40", "settle_40", "camera_top", "hold_capture",
]
TOTAL_BUDGET = 5165


def parse_schedule(source: str) -> list[dict]:
    constants = {
        name: int(value, 0)
        for name, value in re.findall(r"local (KEY_\w+) = (0x[0-9A-Fa-f]+)", source)
    }
    block = source.split("local SCHEDULE = {", 1)[1].split("\n}", 1)[0]
    steps = []
    for name, body in re.findall(r'\{ name = "(\w+)", (.*?) \}', block):
        step = {"name": name}
        for field in FIELDS:
            raw = re.search(rf"{field} = ([^,]+)", body).group(1).strip()
            step[field] = constants[raw] if raw in constants else int(raw, 0)
        steps.append(step)
    return steps


def run_machine(steps: list[dict], engine, limit: int = 20000) -> dict:
    frame = 0
    index = 0
    in_step = 0
    mask = 0
    last_map = None
    events = []
    while frame < limit:
        frame += 1
        if index >= len(steps):
            return {"status": "DONE", "step": steps[-1]["name"], "frame": frame,
                    "mask": mask, "events": events}
        step = steps[index]
        if in_step == 0:
            mask = step["mask"]
            events.append((frame, step["name"], "step", mask, last_map))
        in_step += 1
        map_index, vofs = engine(frame, mask)
        if map_index != last_map:
            events.append((frame, step["name"], "map", mask, map_index))
            if (last_map is not None and step["expect"] >= 0
                    and map_index is not None
                    and map_index != step["expect"]
                    and map_index != step["want_map"]):
                mask = 0
                return {"status": "FAIL", "step": step["name"],
                        "reason": "unexpected_map", "frame": frame, "mask": mask,
                        "events": events}
            last_map = map_index
        met = (
            (step["want_map"] >= 0 and map_index == step["want_map"])
            or (step["want_vofs"] >= 0 and vofs is not None
                and vofs <= step["want_vofs"])
            or (step["hold"] > 0 and in_step >= step["hold"])
        )
        if met:
            events.append((frame, step["name"], "met", mask, map_index))
            index += 1
            in_step = 0
            continue
        if in_step >= step["budget"]:
            mask = 0
            return {"status": "FAIL", "step": step["name"], "reason": "timeout",
                    "frame": frame, "mask": mask, "events": events}
    return {"status": "LIMIT", "step": steps[index]["name"], "frame": frame,
            "mask": mask, "events": events}


def test_the_schedule_is_finite_and_declared():
    steps = parse_schedule(DRIVER.read_text(encoding="utf-8"))
    assert [step["name"] for step in steps] == EXPECTED_STEPS
    assert len(steps) <= 16, "the schedule must stay a finite declared list"
    for step in steps:
        assert step["budget"] >= 1, f"{step['name']} has no frame budget"
        assert step["budget"] >= step["hold"], f"{step['name']} can exhaust its hold"
        assert step["want_map"] >= 0 or step["want_vofs"] >= 0 or step["hold"] > 0, (
            f"{step['name']} has no end condition at all"
        )
    assert sum(step["budget"] for step in steps) == TOTAL_BUDGET


def test_the_tracked_launcher_supplies_the_driver_identity_block():
    """A clean checkout's launcher call must start the driver with no export by hand.

    The driver asserts FINE001_OBSERVER on load, and the audit found no tracked
    launcher exporting it. The launcher now hashes the observer and the staged
    state when -LuaPath is the driver, and clears the exports afterwards.
    """
    source = (ROOT / "tools/runtime/mgba_session.ps1").read_text(encoding="utf-8")
    assert "fine001_route_driver\\.lua$" in source
    assert "$env:FINE001_OBSERVER = $fine001Observer" in source
    assert source.count("FINE001_OBSERVER_SHA256") >= 2
    assert source.count("FINE001_STATE_SHA256") >= 2
    assert "Get-FileHash -Algorithm SHA256 -LiteralPath $StatePath" in source
    assert "'FINE001_OBSERVER', 'FINE001_OBSERVER_SHA256', 'FINE001_STATE_SHA256'" in source


def test_the_happy_path_reaches_every_map_40_probes_observation_step():
    steps = parse_schedule(DRIVER.read_text(encoding="utf-8"))
    state = {"map": 40, "vofs": 200}

    def engine(frame, mask):
        if mask & 0x20 and state["map"] == 40 and frame >= 40:
            state["map"] = 39
        elif mask & 0x20 and state["map"] == 39 and frame >= 400:
            state["map"] = 40
        if state["map"] == 40 and frame >= 500:
            state["vofs"] = 0
        return state["map"], state["vofs"]

    result = run_machine(steps, engine)
    assert result["status"] == "DONE", result
    assert result["step"] == "hold_capture"
    assert result["mask"] == 0, "the run must end with every key released"
    assert state["vofs"] == 0, "the camera must reach the map's top edge"
    assert [event[1] for event in result["events"] if event[2] == "met"] == EXPECTED_STEPS

    window = {(x, y) for y in range(0, 32) for x in range(0, 32)}
    for probe, positions in {
        "p2": [(16, 16)],
        "p3": [(0, 12), (1, 12), (2, 12), (3, 12), (0, 13)],
        "p4b": [(0, 12), (1, 12)],
    }.items():
        assert all(position in window for position in positions), probe


def test_the_camera_step_meets_on_the_measured_top_value():
    """The engine writes 1, not 0, at the map's top edge (seven sessions, stage 2).

    Step 7 must end on that measured value instead of spending its whole budget, or
    the route can never reach the observation hold and no probe can be judged.
    """
    steps = parse_schedule(DRIVER.read_text(encoding="utf-8"))
    assert steps[6]["want_vofs"] == 1
    state = {"map": 40, "vofs": 1}

    def engine(frame, mask):
        if mask & 0x20 and state["map"] == 40 and frame >= 40:
            state["map"] = 39
        elif mask & 0x20 and state["map"] == 39 and frame >= 60:
            state["map"] = 40
        return state["map"], state["vofs"]

    result = run_machine(steps, engine)
    assert result["status"] == "DONE", result
    assert result["mask"] == 0, "the run must end with every key released"
    met = [event for event in result["events"] if event[2] == "met"]
    assert met[-2][1] == "camera_top", met
    assert result["frame"] < TOTAL_BUDGET


def test_a_missed_transition_fails_the_step_that_waits_for_it_and_releases_keys():
    steps = parse_schedule(DRIVER.read_text(encoding="utf-8"))

    def engine(frame, mask):
        return 40, 200

    result = run_machine(steps, engine)
    assert result["status"] == "FAIL"
    assert result["step"] == "leave_to_39"
    assert result["reason"] == "timeout"
    assert result["mask"] == 0, "a failed route must release every key"
    assert result["frame"] == 1 + steps[1]["budget"], (
        "the first step ends on its live condition at frame 1, then the second "
        "step spends exactly its own budget")


def test_an_unexpected_map_fails_at_the_step_that_observed_it():
    steps = parse_schedule(DRIVER.read_text(encoding="utf-8"))

    def engine(frame, mask):
        return (41 if frame >= 50 else 40), 200

    result = run_machine(steps, engine)
    assert result["status"] == "FAIL"
    assert result["step"] == "leave_to_39"
    assert result["reason"] == "unexpected_map"
    assert result["mask"] == 0
    assert result["frame"] == 50
