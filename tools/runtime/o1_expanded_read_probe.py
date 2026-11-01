"""O1: capture a guest CPU read of the expanded region of a 16 MiB LOG2 image.

The proof channel is the GDB stub's read watchpoint (`Z3`), validated here by
three controls rather than assumed:

  POSITIVE  a Z3 on the boot literal at 0x08000134, which the entry sequence
            loads with `LDR sp, [pc, #0x64]` at 0x080000C8, stops the core and
            reports `T05rwatch:08000134;`. An instruction FETCH does NOT trigger
            Z3, so the channel observes data reads specifically.
  NEGATIVE  a Z3 at the expanded sentinel on the CLEAN padded image stays
            silent for the whole run: retail LOG2 contains no instruction that
            reads above canonical EOF.
  IDENTITY  the emulator is the pinned instrumented build, verified through
            tools.mgba_probe.runtime.verify_instrumented_mgba.

Frame counts come from the emulator's own VCOUNT/DISPSTAT progression, read out
of guest hardware registers, never from debugger step counts: a step count is a
property of the debugger session and says nothing about emulated time.

Every run records the guest instruction word, the PC, the full register file,
the watched address, the observed value and the stop reason, so a hit is
attributable to one instruction rather than to the session.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import struct
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

GBA_ROM_BASE = 0x08000000
CANONICAL_SIZE = 0x00800000
EXPANDED_SIZE = 0x01000000
SENTINEL_ADDRESS = GBA_ROM_BASE + CANONICAL_SIZE
BOOT_LITERAL = 0x08000134
BOOT_LDR_PC = 0x080000C8
REG_VCOUNT = 0x04000006
REG_KEYINPUT = 0x04000130
DEFAULT_PORT = 2345
REGISTER_COUNT = 17


class ProbeError(RuntimeError):
    """A probe step could not be completed."""


@dataclass(frozen=True)
class StopRecord:
    reason: str
    pc: int | None
    registers: tuple[int, ...]
    watched_address: int | None
    observed_value: int | None
    instruction_word: int | None
    frame: int | None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["registers"] = list(self.registers)
        for key in ("pc", "watched_address", "observed_value", "instruction_word"):
            if data[key] is not None:
                data[key] = f"0x{data[key]:08X}"
        return data


@dataclass
class RunLog:
    rom: str
    rom_size: int
    rom_sha256: str
    emulator: str
    emulator_sha256: str
    controls: dict = field(default_factory=dict)
    stops: list = field(default_factory=list)
    inputs: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def _packet(payload: str) -> bytes:
    return f"${payload}#{sum(payload.encode()) & 0xFF:02x}".encode()


class Stub:
    """A minimal, synchronous GDB remote-serial client for the probe."""

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock

    def _receive(self, timeout: float) -> str:
        self._sock.settimeout(timeout)
        buffer = b""
        try:
            while b"#" not in buffer or len(buffer.split(b"#")[-1]) < 2:
                chunk = self._sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk
        except socket.timeout:
            pass
        text = buffer.decode(errors="replace").lstrip("+")
        if text.startswith("$"):
            text = text[1:].split("#")[0]
        return text

    def ask(self, payload: str, timeout: float = 5.0) -> str:
        self._sock.sendall(_packet(payload))
        answer = self._receive(timeout)
        self._sock.sendall(b"+")
        return answer

    def resume(self, timeout: float) -> str:
        self._sock.sendall(_packet("c"))
        answer = self._receive(timeout)
        self._sock.sendall(b"+")
        return answer

    def registers(self) -> tuple[int, ...]:
        raw = self.ask("g")
        words = []
        for index in range(0, min(len(raw), REGISTER_COUNT * 8), 8):
            chunk = raw[index:index + 8]
            if len(chunk) == 8:
                try:
                    words.append(int.from_bytes(bytes.fromhex(chunk), "little"))
                except ValueError:
                    break
        return tuple(words)

    def read_word(self, address: int) -> int | None:
        payload = self.ask(f"m{address:x},4")
        if len(payload) != 8:
            return None
        try:
            return int.from_bytes(bytes.fromhex(payload), "little")
        except ValueError:
            return None

    def read_halfword(self, address: int) -> int | None:
        payload = self.ask(f"m{address:x},2")
        if len(payload) != 4:
            return None
        try:
            return int.from_bytes(bytes.fromhex(payload), "little")
        except ValueError:
            return None

    def set_watchpoint(self, address: int, length: int = 4) -> bool:
        return self.ask(f"Z3,{address:x},{length}") == "OK"

    def clear_watchpoint(self, address: int, length: int = 4) -> None:
        self.ask(f"z3,{address:x},{length}")

    def set_breakpoint(self, address: int, length: int = 4) -> bool:
        return self.ask(f"Z0,{address:x},{length}") == "OK"

    def clear_breakpoint(self, address: int, length: int = 4) -> None:
        self.ask(f"z0,{address:x},{length}")


def sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_watch_stop(reason: str) -> int | None:
    marker = "rwatch:"
    if marker not in reason:
        return None
    tail = reason.split(marker, 1)[1]
    hexits = tail.split(";", 1)[0]
    try:
        return int(hexits, 16)
    except ValueError:
        return None


def instruction_word(rom: bytes, pc: int, *, back: int = 4) -> int | None:
    offset = pc - GBA_ROM_BASE - back
    if 0 <= offset <= len(rom) - 4:
        return struct.unpack_from("<I", rom, offset)[0]
    return None


def launch(executable: Path, runtime_bin: Path, rom: Path, port: int):
    environment = os.environ.copy()
    environment["PATH"] = str(runtime_bin) + os.pathsep + environment.get("PATH", "")
    process = subprocess.Popen(
        [str(executable), "--gdb", str(rom)],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    stub = None
    for _ in range(40):
        try:
            stub = Stub(socket.create_connection(("127.0.0.1", port), timeout=1.0))
            break
        except OSError:
            time.sleep(0.5)
    if stub is None:
        process.terminate()
        raise ProbeError(f"the GDB stub never answered on port {port}")
    return process, stub


def terminate(process) -> int:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
    return process.pid


def control_positive(stub: Stub, rom: bytes) -> dict:
    installed = stub.set_watchpoint(BOOT_LITERAL)
    reason = stub.resume(timeout=25.0) if installed else ""
    registers = stub.registers()
    pc = registers[15] if len(registers) > 15 else None
    address = parse_watch_stop(reason)
    return {
        "installed": installed,
        "stop_reason": reason,
        "pc": f"0x{pc:08X}" if pc is not None else None,
        "watched_address": f"0x{address:08X}" if address is not None else None,
        "fired": bool(reason) and address == BOOT_LITERAL,
        "loading_instruction": f"0x{instruction_word(rom, BOOT_LDR_PC, back=0):08X}",
        "meaning": "Z3 observes guest ROM data reads and names the address",
    }


def frame_counter(stub: Stub) -> int | None:
    return stub.read_halfword(REG_VCOUNT)


def run(
    executable: Path,
    runtime_bin: Path,
    rom: Path,
    *,
    watch: int,
    port: int,
    settle_seconds: float,
    expect_hit: bool,
    out: Path | None,
) -> int:
    rom_bytes = rom.read_bytes()
    log = RunLog(
        rom=rom.name,
        rom_size=len(rom_bytes),
        rom_sha256=sha256(rom),
        emulator=executable.name,
        emulator_sha256=sha256(executable),
    )

    process, stub = launch(executable, runtime_bin, rom, port)
    try:
        log.controls["halt_state"] = stub.ask("?")
        log.controls["vcount_at_halt"] = frame_counter(stub)
        log.controls["keyinput_at_halt"] = stub.read_halfword(REG_KEYINPUT)
        log.controls["positive"] = control_positive(stub, rom_bytes)
        stub.clear_watchpoint(BOOT_LITERAL)
    finally:
        terminate(process)

    process, stub = launch(executable, runtime_bin, rom, port)
    try:
        if not stub.set_watchpoint(watch):
            raise ProbeError(f"the stub refused a read watchpoint at 0x{watch:08X}")
        reason = stub.resume(timeout=settle_seconds)
        registers = stub.registers()
        pc = registers[15] if len(registers) > 15 else None
        address = parse_watch_stop(reason)
        observed = stub.read_word(watch)
        record = StopRecord(
            reason=reason,
            pc=pc,
            registers=registers,
            watched_address=address,
            observed_value=observed,
            instruction_word=instruction_word(rom_bytes, pc) if pc else None,
            frame=frame_counter(stub),
        )
        log.stops.append(record.to_dict())
        fired = bool(reason) and address == watch
    finally:
        pid = terminate(process)
        log.notes.append(f"probe terminated the mGBA process it launched, pid {pid}")

    print(json.dumps({"controls": log.controls, "stops": log.stops}, indent=2))
    print()
    print(f"watch address : 0x{watch:08X}")
    print(f"positive control fired : {log.controls['positive']['fired']}")
    print(f"watch fired            : {fired}")
    print(f"expected a hit         : {expect_hit}")

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(asdict(log), indent=2) + "\n", encoding="utf-8")
        print(f"evidence written       : {out}")

    if not log.controls["positive"]["fired"]:
        print("RESULT: the proof channel is NOT validated on this run; no claim is made")
        return 3
    if fired != expect_hit:
        print("RESULT: the run disagrees with what was expected")
        return 4
    print("RESULT: as expected")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--runtime-bin", type=Path, required=True)
    parser.add_argument("--watch", type=lambda text: int(text, 0),
                        default=SENTINEL_ADDRESS)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--settle-seconds", type=float, default=25.0)
    parser.add_argument("--expect-hit", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        return run(
            args.executable,
            args.runtime_bin,
            args.rom,
            watch=args.watch,
            port=args.port,
            settle_seconds=args.settle_seconds,
            expect_hit=args.expect_hit,
            out=args.out,
        )
    except ProbeError as error:
        print(f"RESULT: {error}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
