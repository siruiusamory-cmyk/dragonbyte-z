"""The build report states a count by default and lists offsets only on request.

A 29-byte span or a relocated 453-row map table can mint hundreds of changed
offsets, and a log whose tail is a wall of `0x` words hides the digest and the
result line. `--verbose` is the opt-in that lists them.
"""

from __future__ import annotations

from types import SimpleNamespace

from tools.webfoot.cli import _print_build


def result_with_one_change():
    change = SimpleNamespace(
        owner="conversation:0x087809EC/entry:0",
        reason="authored conversation script",
        offset=0x78098F,
        size=5,
        old=bytes.fromhex("0002110000"),
        new=bytes.fromhex("00e4021d00"),
    )
    manifest = SimpleNamespace(
        base_profile_id="buus_fury_usa_rev0_01c1707f",
        base_sha256="940ad5f0",
        output_sha256="f5e19618",
        changes=(change,),
    )
    return SimpleNamespace(
        project_name="scene",
        manifest=manifest,
        output_path="scene.gba",
        manifest_path=None,
    )


def test_the_default_report_counts_changed_bytes_without_listing_them(capsys):
    _print_build(result_with_one_change())
    output = capsys.readouterr().out
    assert "bytes changed: 3 (pass --verbose to list them)" in output
    assert "0x00780990" not in output
    assert "0x00780991" not in output
    assert "0x00780992" not in output
    assert "Semantic edits applied: 1" in output
    assert "COMPLETE" in output


def test_verbose_lists_every_changed_offset(capsys):
    _print_build(result_with_one_change(), verbose=True)
    output = capsys.readouterr().out
    assert "bytes changed: 0x00780990, 0x00780991, 0x00780992" in output
    assert "pass --verbose" not in output


def test_the_build_command_declares_the_switch():
    from tools.webfoot.cli import build_parser

    args = build_parser().parse_args(
        ["build", "project", "--rom", "rom.gba", "--output", "out.gba", "--verbose"]
    )
    assert args.verbose is True
    plain = build_parser().parse_args(
        ["build", "project", "--rom", "rom.gba", "--output", "out.gba"]
    )
    assert plain.verbose is False
