# Install and launch on Windows

There are two ways to get DragonByte Z. Most people want the first.

No ROM or game data is included either way. You supply your own legally obtained ROM.

## Option 1: download the program

Nothing to install. You do not need Python, Git or a terminal.

1. Open the [latest release](https://github.com/siruiusamory-cmyk/dragonbyte-z/releases/latest)
   and download the `.zip` file under **Assets**.
2. Right-click it, choose **Extract All**, and pick a folder you can find again.
   Keep the whole folder together: the program needs the files beside it.
3. Double-click **`DragonByte Z.exe`**.

The program is not code-signed, so Windows may show "Windows protected your PC" the
first time. Choose **More info**, then **Run anyway**.

To play what you build, install [mGBA](https://mgba.io/). The first time you press
Play, the program finds mGBA or asks you where `mGBA.exe` is.

To update, download the newer release and extract it to a new folder. Your projects
live in their own folders and are not touched.

Next: the [user guide](docs/creator.md).

## Option 2: run from the source code

This route is for developers and for anyone who wants the command-line SDK.

### Requirements

- Windows 10 or 11, PowerShell 5.1 or newer, and Git.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) on `PATH`.
  Setup installs Python 3.12 if needed and creates a local `.venv`.
- mGBA is optional for installation; running generated ROMs needs an emulator.

### Clone and install

Run in PowerShell from a directory where you keep projects:

```powershell
git clone https://github.com/siruiusamory-cmyk/dragonbyte-z.git
cd dragonbyte-z
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1 -SkipUpstreams
.\.venv\Scripts\webfoot.exe --help
.\.venv\Scripts\dragonbyte-z.exe
```

The final command opens DragonByte Z, the same program as the download. It is a
GUI command, so do not use `--help` to test it. Launch the same command again in
later sessions from the clone directory, or double-click `DragonByte Z.cmd`.
Activation is optional when using these explicit paths.

`setup.ps1` runs `uv sync --locked` with the `dev`, `workbench` and `research`
extras. `-SkipUpstreams` omits external research-source clones; the SDK and the
program do not need those clones. Contributors investigating an upstream may run
setup without that switch; sources are pinned in [`upstreams.lock`](upstreams.lock).
The separate `packaging` extra is for building executables, not using the SDK.

### Identify your ROM

Keep the original read-only and outside version control. The ignored `roms`
directory is available for local inputs, but never publish its contents.

```powershell
.\.venv\Scripts\webfoot.exe identify "<path-to-your-ROM.gba>"
```

A supported exact image reports its profile and `VERIFIED`, exit 0. Unknown
images are refused (`UNKNOWN`, exit 1); identity/metadata conflicts exit 2.
A matching title alone is insufficient. See [supported profiles](docs/rom-profiles.md)
and the mandatory [ROM safety contract](docs/ROM_SAFETY.md).

SDK project and build workflows are covered by the
[usage journeys](docs/journeys/README.md). Always choose a new output path and
retain the generated provenance manifest.

### Other entry points

```powershell
.\.venv\Scripts\python.exe -m tools.webfoot --help
.\.venv\Scripts\buufury-text.exe
.\.venv\Scripts\python.exe -m tools.webfoot.workbench
```

These are respectively the SDK command line, the dedicated text editor, and the
older engineering Workbench. `python -m tools.webfoot.cli` is not an executable
entry point and prints nothing.

### Troubleshooting

- If `uv` is missing, install it using its linked instructions and reopen PowerShell.
- If an executable is missing, confirm setup completed successfully and that you
  are in the clone root. Do not install globally to work around an incomplete setup.
- An unrecognized ROM is not permission to change its identity in the catalogue.
- ROM editing and emulator behavior require private inputs. CLI help and
  synthetic tests can be checked without a ROM; neither proves a real game edit.

The [newcomer walkthrough](docs/newcomer.md) preserves command-level evidence
and clearly distinguishes executed checks from unexecuted game workflows.
For development see [Contributing](CONTRIBUTING.md) and the
[documentation index](docs/README.md).
