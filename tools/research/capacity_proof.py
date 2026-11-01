"""TOOLKIT-028 bounded verification of ONE narrow candidate window.

This is a research adapter, exactly like `free_space_audit`. It NEVER promotes
anything by itself: it emits a verdict record, and a human review decides whether
that verdict justifies a profile `free_regions` declaration. Production still
refuses any declaration whose status is not `CONFIRMED`
(`tools/webfoot/profile.py:_free_regions`).

The question it answers is deliberately smaller than TOOLKIT-011's. TOOLKIT-011
asked whether the whole ~292 KB upstream tail is allocatable and correctly said
NO, because 516 unresolved candidate references land inside it. This asks whether
one BOUNDED WINDOW of that tail is provably clear of every one of those candidates
and of every other modelled use. A window survives only if all of the following
hold, and each is reported as its own field so a reviewer can see the basis:

  * `fill`            - every byte in the window is the tail's `FF` fill;
  * `known_inbound`   - no CONFIRMED/DECLARED reference in the production graph
                        targets any byte of the window;
  * `known_overlap`   - no modelled anchor or declared table overlaps it;
  * `candidate_target`- no CANDIDATE reference observation targets any byte of it,
                        INCLUDING interior bytes, at any alignment;
  * `candidate_source`- no CANDIDATE observation is SOURCED inside it, so writing
                        the window cannot alter a word some unknown consumer reads
                        as a pointer;
  * `margin`          - the window keeps a stated clearance from the nearest
                        candidate target on each side, so a structure that begins
                        at an unresolved candidate and runs on still misses it;
  * `bounds`          - the window lies inside the image and clear of the header.

`candidate_target` is the load-bearing one and it is NOT a weakening of TOOLKIT-011's
policy. Every one of the 516 observations stays exactly as blocking as it was; this
only establishes that a specific window contains none of them. An unresolved candidate
still blocks the bytes it points at, forever, until separate evidence resolves it.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import struct

from tools.webfoot.binary import FileOffset, GbaRomAddress
from tools.webfoot.layout import RomRange

#: The GBA cartridge header occupies the first 0xC0 bytes and the toolkit's own
#: declared header/startup annotation runs to 0x158; nothing is verified below it.
HEADER_END = 0x158

#: Bytes of clearance required between the window and the nearest candidate-reference
#: target on either side. A candidate is an unresolved pointer-shaped word: if it IS
#: real, some structure begins at its target, and that structure has unknown length.
#: The margin means a window is never carved flush against one.
DEFAULT_MARGIN = 0x400


def scan_candidate_observations(image, span):
    """Every u32 in the image, at EVERY byte position, that addresses `span`.

    Same method and same non-promotion semantics as
    `free_space_audit.candidate_report`: unaligned sources are included, because
    an unaligned window is only evidence that overlapping reads cannot all be
    authoritative - it is not evidence that the value is meaningless.
    """
    span.validate(len(image))
    start, end = span.start.value, span.end
    hits = []
    for source in range(len(image) - 3):
        raw = struct.unpack_from("<I", image, source)[0]
        try:
            target = GbaRomAddress(raw).to_file_offset(len(image))
        except ValueError:
            continue
        if start <= target < end:
            hits.append({"source": source, "target": target,
                         "source_word_aligned": source % 4 == 0})
    return hits


def verify_window(image, window, *, observations, owned, references,
                  margin=DEFAULT_MARGIN, fill_byte=0xFF):
    """Decide ONE window against every stated factor. Fails closed on any failure.

    `observations` must cover AT LEAST the window plus `margin` on both sides;
    a narrower scan would silently weaken the margin check, so callers pass the
    tail-wide observation set rather than a window-local one.
    """
    window.validate(len(image))
    start, end = window.start.value, window.end
    checks = {}

    checks["bounds"] = {
        "pass": start >= HEADER_END and end <= len(image) and start < end,
        "window_start": start, "window_end": end, "image_size": len(image),
        "header_end": HEADER_END,
    }

    histogram = dict(sorted(Counter(image[start:end]).items()))
    checks["fill"] = {"pass": set(histogram) == {fill_byte},
                      "expected_fill": fill_byte, "byte_histogram": histogram}

    inbound = [r for r in references if start <= r["target"] < end]
    checks["known_inbound"] = {"pass": not inbound, "count": len(inbound),
                               "references": inbound[:16]}

    overlaps = [r for r in owned if r["start"] < end and r["end"] > start]
    checks["known_overlap"] = {"pass": not overlaps, "count": len(overlaps),
                               "annotations": overlaps[:16]}

    inside_target = [o for o in observations if start <= o["target"] < end]
    checks["candidate_target"] = {"pass": not inside_target, "count": len(inside_target),
                                  "observations": inside_target[:16]}

    inside_source = [o for o in observations if start <= o["source"] < end]
    checks["candidate_source"] = {"pass": not inside_source, "count": len(inside_source),
                                  "observations": inside_source[:16]}

    targets = sorted({o["target"] for o in observations})
    below = [t for t in targets if t < start]
    above = [t for t in targets if t >= end]
    clearance_below = start - max(below) if below else None
    clearance_above = min(above) - end if above else None
    checks["margin"] = {
        "pass": ((clearance_below is None or clearance_below >= margin)
                 and (clearance_above is None or clearance_above >= margin)),
        "required": margin,
        "nearest_candidate_target_below": max(below) if below else None,
        "nearest_candidate_target_above": min(above) if above else None,
        "clearance_below": clearance_below, "clearance_above": clearance_above,
    }

    verdict = "VERIFIED" if all(c["pass"] for c in checks.values()) else "REJECTED"
    return {"verdict": verdict, "start": start, "end": end, "size": window.size,
            "checks": checks,
            "failed_checks": sorted(k for k, c in checks.items() if not c["pass"])}


def positive_controls(image, observations, owned, references, controls):
    """Prove the scanner DETECTS use, by running it at windows known to be used.

    A negative result is only evidence if the same procedure returns a positive on
    live structures. Each control names a window this project has independently
    modelled as occupied and asserts the verifier REJECTS it, failing at least the
    named checks. A control that came back VERIFIED would mean the scanner is blind
    and the whole report is void.
    """
    results = []
    for name, span, expect in controls:
        report = verify_window(image, span, observations=observations, owned=owned,
                               references=references)
        failed = set(report["failed_checks"])
        results.append({"control": name, "start": span.start.value, "end": span.end,
                        "verdict": report["verdict"],
                        "failed_checks": sorted(failed),
                        "expected_to_fail_at_least": sorted(expect),
                        "pass": report["verdict"] == "REJECTED" and set(expect) <= failed})
    return results


def report(path, window, *, catalog_path=None, margin=DEFAULT_MARGIN):
    """Full verdict record for one window, with its positive controls.

    The annotation/reference model comes from `free_space_audit.build_model`, so
    these negatives are measured against exactly the model that produced
    TOOLKIT-011's positives rather than a second, differently-shaped one.
    """
    from tools.research.free_space_audit import build_model

    model = build_model(path, catalog_path=catalog_path)
    image, owned, references, profile = (model["image"], model["owned"],
                                         model["references"], model["profile"])
    tail = model["tail"]
    observations = scan_candidate_observations(image, tail)
    verdict = verify_window(image, window, observations=observations, owned=owned,
                            references=references, margin=margin)
    controls = positive_controls(image, observations, owned, references,
                                 model["controls"](image))
    return {
        "profile_id": profile.id,
        "base_sha256": profile.sha256,
        "tail_scanned": {"start": tail.start.value, "end": tail.end, "size": tail.size},
        "candidate_observations_in_tail": len(observations),
        "distinct_candidate_targets": len({o["target"] for o in observations}),
        "window": verdict,
        "positive_controls": controls,
        "positive_controls_pass": all(c["pass"] for c in controls),
        "decision": ("WINDOW_VERIFIED_PENDING_REVIEW"
                     if verdict["verdict"] == "VERIFIED" and all(c["pass"] for c in controls)
                     else "NOT_PROMOTED"),
        "limits": ("Bounded window only. Every unresolved candidate outside this window "
                   "remains blocking. This report cannot itself declare capacity; a "
                   "reviewed profile free_regions entry does."),
    }


def tail_windows(image, span, *, observations, owned, references,
                 margin=DEFAULT_MARGIN):
    """Every window the tail offers, each decided by the same seven checks.

    The tail is not searched at every offset. A window can only survive inside the
    span (a `fill` failure elsewhere in it is already known), only where no
    candidate target, candidate source or known reference target falls, and the
    margin rule then fixes the widest extent it may take between those blockers. So
    the blocker-free gaps ARE every maximal candidate, and each is reported: the
    gap itself when the required clearance leaves no room inside it, and the
    margin-clear interior otherwise. Every record goes through `verify_window`, so
    this cannot report a pass the single-window proof would refuse.

    `observations` must cover at least the span plus `margin` below and above it;
    a narrower set would silently weaken `margin`.
    """
    start, end = span.start.value, span.end
    blockers = set()
    for observation in observations:
        for key in ("target", "source"):
            if start <= observation[key] < end:
                blockers.add(observation[key])
    blockers.update(r["target"] for r in references if start <= r["target"] < end)
    targets = sorted({o["target"] for o in observations})
    gaps = []
    cursor = start
    for point in sorted(blockers):
        if point > cursor:
            gaps.append((cursor, point))
        cursor = point + 1
    if end > cursor:
        gaps.append((cursor, end))

    records = []
    for gap_start, gap_end in gaps:
        begin = max([gap_start] + [t + margin for t in targets
                                   if t < gap_start and t + margin > gap_start])
        finish = min([gap_end] + [t - margin for t in targets
                                  if t >= gap_end and t - margin < gap_end])
        window = (RomRange(FileOffset(gap_start), gap_end - gap_start)
                  if finish <= begin else RomRange(FileOffset(begin), finish - begin))
        verdict = verify_window(image, window, observations=observations, owned=owned,
                                references=references, margin=margin)
        verdict["gap_start"] = gap_start
        verdict["gap_end"] = gap_end
        records.append(verdict)
    return records


def tail_report(path, *, catalog_path=None, margin=DEFAULT_MARGIN):
    """The full verdict record for the whole tail of this image's modelled profile.

    `report` answers one window; this answers what the tail actually yields. It
    reuses the same model, the same candidate scan and the same verifier, and it
    reports each window with all seven checks as its own field. The observation
    scan is widened by `margin` on both sides of the tail because the margin check
    has to see the nearest candidate BELOW the tail as well as above it; a target
    further below than that is more than the required clearance away by
    construction, so the widening is sufficient and is not an extra check.
    """
    from tools.research.free_space_audit import build_model

    model = build_model(path, catalog_path=catalog_path)
    image, owned, references, profile = (model["image"], model["owned"],
                                         model["references"], model["profile"])
    span = model["tail"]
    scan_start = max(0, span.start.value - margin)
    scan = RomRange(FileOffset(scan_start),
                    min(len(image), span.end + margin) - scan_start)
    observations = scan_candidate_observations(image, scan)
    windows = tail_windows(image, span, observations=observations, owned=owned,
                           references=references, margin=margin)
    passing = [w for w in windows if w["verdict"] == "VERIFIED"]
    controls = positive_controls(image, observations, owned, references,
                                 model["controls"](image))
    kinds = Counter(row["kind"] for row in owned)
    return {
        "profile_id": profile.id,
        "base_sha256": profile.sha256,
        "tail_scanned": {"start": scan.start.value, "end": scan.end, "size": scan.size},
        "window_span": {"start": span.start.value, "end": span.end, "size": span.size},
        "candidate_observations_in_tail": len(observations),
        "distinct_candidate_targets": len({o["target"] for o in observations}),
        "model_inventory": {
            "owned_rows": len(owned),
            "owned_bytes": sum(row["end"] - row["start"] for row in owned),
            "owned_by_kind": dict(sorted(kinds.items())),
            "references": len(references),
            "distinct_reference_targets": len({r["target"] for r in references}),
        },
        "windows": windows,
        "passing_window_count": len(passing),
        "total_passing_bytes": sum(w["size"] for w in passing),
        "largest_passing_window": (max(passing, key=lambda w: (w["size"], -w["start"]))
                                   if passing else None),
        "positive_controls": controls,
        "positive_controls_pass": all(c["pass"] for c in controls),
        "decision": ("WINDOWS_VERIFIED_PENDING_REVIEW"
                     if passing and all(c["pass"] for c in controls)
                     else "NOT_PROMOTED"),
        "limits": ("Tail windows only. Every unresolved candidate outside a window "
                   "remains blocking, and a pass is only as strong as the modelled "
                   "reference graph it was measured against. This report cannot itself "
                   "declare capacity; a reviewed profile free_regions entry does."),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--start", type=lambda v: int(v, 0))
    parser.add_argument("--size", type=lambda v: int(v, 0))
    parser.add_argument("--margin", type=lambda v: int(v, 0), default=DEFAULT_MARGIN)
    parser.add_argument("--catalog", type=Path, default=None)
    parser.add_argument("--scan-tail", action="store_true",
                        help="scan the whole modelled tail instead of one window")
    args = parser.parse_args()
    if args.scan_tail:
        print(json.dumps(tail_report(args.rom, catalog_path=args.catalog,
                                     margin=args.margin), indent=2, sort_keys=True))
    else:
        if args.start is None or args.size is None:
            parser.error("--start and --size are required unless --scan-tail is given")
        print(json.dumps(report(args.rom, RomRange(FileOffset(args.start), args.size),
                                catalog_path=args.catalog, margin=args.margin),
                         indent=2, sort_keys=True))
