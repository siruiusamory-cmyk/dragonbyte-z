# Install

The Webfoot SDK runs from a clone of this repository. It installs into a project
`.venv` and puts three console scripts on that environment's `PATH`:
`webfoot` (the command line), `dragonbyte-z` (the desktop editor) and
`buufury-text` (the text editor). No game data is included: you supply your own
verified ROM, and the toolkit refuses an image it cannot identify.

## Prerequisites

| Need | Why | Checked here |
| --- | --- | --- |
| Windows 10 or 11 with PowerShell 5.1 or PowerShell 7 | `scripts\setup.ps1` and `scripts\test.ps1` are PowerShell scripts | PowerShell 7.6.9 on Windows |
| Git | the clone and every provenance record | Git 2.55.0 |
| [`uv`](https://docs.astral.sh/uv/) on `PATH` | `setup.ps1` refuses without it, and it creates the environment from the locked set | uv 0.11.15 |
| Python 3.12 | `pyproject.toml` declares `requires-python = ">=3.12"`; `setup.ps1` installs 3.12 through `uv` when the host has none | 3.12.10 |
| Your own legally obtained ROM, outside version control | every read path starts from a verified image; the repository ships none | see [Provide a ROM](#provide-a-rom) |
| mGBA, optional | the Run action and the runtime research tools only | not on `PATH` here; not required to install |

## Install from a clone

```powershell
git clone <repository-url>
cd <clone>
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\.venv\Scripts\Activate.ps1
```

`setup.ps1` runs two commands, both taken from the script itself:

```text
uv python install 3.12                     (only when the host has no 3.12)
uv sync --locked --extra dev --extra workbench --extra research \
        --project <clone> --python <selector>
```

The script passes `--extra` once per extra, and `--python` is the existing
`.venv` interpreter, or the literal `3.12` when it had to install one.

`--locked` installs exactly the versions in `uv.lock`. The three extras are the
set CI installs, and they are the ones the documented gates need: `dev` for the
test tooling, `workbench` for PySide6, `research` for capstone. `packaging`
(PyInstaller) is deliberately not part of setup: it is an owner-run release step,
and the `packaging` extra in `pyproject.toml` declares it.

### What was and was not executed for this page

The two commands above were **not executed while this page was written**: this
environment forbids installs, and it already had the prerequisites. What was
executed is the module form of the same entry point, from the clone root:

```powershell
python -m tools.webfoot --help
```

```text
exit=0
usage: webfoot [-h] [--profiles PROFILES]
               {placement,entity,event,graphics,atlas,relocation-proof,identify,...}
```

So the install method is stated from the script and the lock file, and the entry
point is proven by execution. A reader on a clean machine runs the two commands
above; nothing else on this page depends on an unstated assumption.

## Verify the install

With the environment active:

```powershell
webfoot --help
```

Expected: the same usage text, exit 0. This **installed console-script form was
not executed here** (nothing was installed); the module form above was. If
`webfoot` is not on `PATH`, the environment is not active, or `uv sync` did not
reach the console-script step.

### The entry point that looks dead and is not

`tools\webfoot\cli.py` carries `main` and the whole command tree, and it has no
`if __name__ == "__main__"` block. `tools\webfoot\__main__.py` is what makes the
package runnable. The consequence, measured:

| command | output | exit |
| --- | --- | --- |
| `python -m tools.webfoot --help` | the usage text | 0 |
| `python -m tools.webfoot.cli --help` | **nothing at all** | 0 |
| `webfoot --help` | not found, because nothing is installed here | not run |

Use `webfoot` (installed) or `python -m tools.webfoot` (from the clone root).
Never document or run the `.cli` form and conclude the module is broken.

## Provide a ROM

The repository tracks no ROM and no game data. Keep your own image outside
version control; the ignored `roms\` directory is the conventional place.

```powershell
webfoot identify ".\roms\<your image>.gba"
```

Identification is cryptographic, not a title match: `config\roms.yaml` is the
authoritative catalogue, and a profile is accepted only when its configured
SHA-256 and every other configured hash and metadata constraint match. On a
match the command prints the profile id, the status `VERIFIED`, and exits 0. A
file that matches no configured identity prints `UNKNOWN` with the reason and
exits 1; an identity that matches while configured metadata conflicts prints
`CONFLICT` with the reason and every conflict, and exits 2. Measured refusal, on
a file that is not a ROM:

```text
$ python -m tools.webfoot identify README.md
...
Header Checksum: 0x65 (calculated 0xB7, INVALID)
Basic Header: INVALID

Profile:
NONE

Status:
UNKNOWN
Reason: no configured cryptographic identity matched
exit=1
```

A path that does not exist exits 2 with `error: ROM does not exist: <path>`.
[`docs/rom-profiles.md`](docs/rom-profiles.md) lists the configured profiles and
their digests.

## Where to go next

- [`docs/newcomer.md`](docs/newcomer.md) - clone to a verified modification, one
  stage at a time, with what was executed and what was not.
- [`docs/README.md`](docs/README.md) - the documentation index.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) - the change path and the review gate.
