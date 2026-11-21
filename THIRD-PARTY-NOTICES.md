# Third-Party Notices

The Webfoot SDK and the other original code in this repository are licensed
under MPL-2.0; see [`LICENSE`](LICENSE).

**That root license does not relicense third-party material.** Each upstream
listed here keeps its own license and its own copyright holders. Where a file in
this repository incorporates or modifies third-party material, the upstream
license governs that material regardless of the root license.

This file records the upstreams that place an obligation on this repository or
that materially informed shipped code. Machine-pinned revisions for every
upstream the project consults live in [`upstreams.lock`](upstreams.lock), and
the per-upstream inspection record lives in
[`docs/upstream-audit.md`](docs/upstream-audit.md).

---

## DragonByteZ - MIT

- **Upstream:** <https://github.com/spicybung/DragonByteZ>
- **Pinned revision:** `b2691209fa873cc0c1d7aa9cdea7c1da4430afe4` (`upstreams.lock`)
- **Upstream license:** MIT, stated in the upstream root `LICENSE`.
- **Affected file in this repository:** `tools/webfoot/formats/webfoot_lz.py`

### What is incorporated

`tools/webfoot/formats/webfoot_lz.py` implements the Webfoot compression
container. Its bit grammar is a **cross-language derivative** of upstream
`src/compression.cpp` rather than an independent derivation, and the module says
so in its own docstring. Specifically, the match-length/distance ladder is
carried over from the upstream implementation: the thresholds (`0x10000`,
`0x37FF`, `0x027F`, `0x007F`) and their bias values are not derivable from first
principles and are reproduced deliberately.

The module's source-level provenance comments are the primary record of this and
are intentionally preserved. Do not remove them.

The Python implementation, its container/header handling, its encoder, its error
model, and its tests are this project's own work. Correctness was independently
verified against the canonical ROM before promotion: all 7,390 distinct
container offsets reachable by a piece decode without failure, and every
decoded length matches the width times height that the referring piece record
independently declares (`docs/research/GRAPHICS_FORMAT.md`).

### Required notice

The following notice is reproduced from the upstream `LICENSE` in satisfaction
of the MIT license's condition that the copyright notice and permission notice
be included in all copies or substantial portions of the Software:

```
MIT License

Copyright (c) 2026 DragonByteZ contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## mGBA - MPL-2.0

- **Upstream:** <https://github.com/mgba-emu/mgba>
- **Version:** 0.10.5, upstream commit `26b7884bc25a5933960f3cdcd98bac1ae14d42e2`
  (pinned and documented in `tools/mgba_probe/README.md`)
- **Upstream license:** MPL-2.0, in the upstream `LICENSE`.
- **Upstream copyright:** mGBA is Copyright (c) 2013-2022 Jeffrey Pfau.
- **Affected file in this repository:**
  `tools/mgba_probe/mgba-0.10.5-log1-read-probe.patch`

### What is incorporated

The file is a unified-diff patch, not a redistribution of the mGBA tree. The
upstream checkout and any built emulator binary stay under ignored `extern/` and
`build/` and are not part of this repository.

The patch modifies these MPL-2.0-covered upstream files:

| Upstream file | Upstream copyright line |
| --- | --- |
| `include/mgba/internal/gba/gba.h` | Copyright (c) 2013-2016 Jeffrey Pfau |
| `src/debugger/gdb-stub.c` | Copyright (c) 2013-2016 Jeffrey Pfau |
| `src/gba/gba.c` | Copyright (c) 2013-2015 Jeffrey Pfau |
| `src/gba/memory.c` | Copyright (c) 2013-2016 Jeffrey Pfau |
| `src/gba/test/core.c` | Copyright (c) 2013-2016 Jeffrey Pfau |

Because it is a diff, the patch also carries unchanged upstream context lines
from those files. Both the context and the modifications to those files are
MPL-2.0-covered material.

### Licensing scope

MPL-2.0 is a file-level (weak) copyleft. The files listed above remain governed
by MPL-2.0 in both their upstream and their modified form. The root MPL-2.0
license of this repository does not supersede, relicense, or extend any
additional grant over mGBA material; it happens to be the same license, and that
coincidence changes nothing about which copyright holders govern those files.

Anyone redistributing the patch, or a build produced by applying it, is
redistributing modified MPL-2.0 Covered Software and takes on MPL-2.0's source
availability obligations for those files.

The upstream Exhibit A notice, present in the patched files themselves, is:

```
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.
```

---

## BuusFuryToolkit - provenance evidence, no explicit license

- **Upstream:** <https://github.com/yoav74/BuusFuryToolkit>
- **Pinned revision:** `4353f6a23aa4ac980f1ed42a2c65bc281fa45cc7` (`upstreams.lock`)
- **Upstream license:** none identified by this project. `UNKNOWN`
  (`docs/upstream-audit.md`).
- **Affected file in this repository:** `tools/webfoot/formats/stat_tables.py`

### What was used, and what was not

No BuusFuryToolkit implementation was copied, and this project claims no
redistribution rights over any BuusFuryToolkit material. Nothing from that
upstream is vendored into this repository.

What was used is **layout and naming evidence**: the header lines of the
upstream's `Enemies.txt` and `Base Stats.txt` state field orders, and the
upstream README documents the `ROM offset + 0x08000000` addressing convention.

The corresponding behavior was independently verified against the canonical
local ROM before the module was written (DATA-001). The verified extent, record
stride, and field decode were established by reading the ROM directly - upstream
lists named offsets individually and never states where either table begins or
ends, so the bounds in this repository are this project's measurement, not the
upstream's word.

Semantics stay labelled by evidence level, per
[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md):

- `CONFIRMED` - record stride, table extent, and field decode, established from
  the canonical ROM.
- `INFERRED` - the human-readable *names* attached to individual records. Those
  come from BuusFuryToolkit's author and were not re-derived. The numbers are
  trustworthy; a name is a label of convenience.

Because the upstream has no explicit license, this repository depends on it only
as documentation consulted during research, not as a source of code or data.

---

## Tabler Icons - MIT

- **Upstream:** <https://github.com/tabler/tabler-icons>
- **Pinned revision:** `a4ce1404bc6d24d3c365afe7b258d6bf6f48d62d` (the `main` commit the outline SVGs were taken from)
- **Upstream license:** MIT, stated in the upstream root `LICENSE`.
- **Affected files in this repository:** `tools/buufury_text/icons/*.svg`

### What is incorporated

Nineteen outline icons, copied unmodified: `search`, `pencil`, `arrow-up-right`,
`square-x`, `check`, `lock`, `copy`, `folder-open`, `device-floppy`,
`arrow-back-up`, `arrow-forward-up`, `link`, `chevron-down`, `photo`, `x`,
`external-link`, `refresh`, `filter`, `minus`. They are the application's toolbar, list and
dialog icons. Tabler draws them on a 24x24 grid with a 2 px stroke and the
application renders them at 16 logical pixels, so the set stays legible at the
density the visual specification calls for without a bitmap pack per scale.

### Required notice

The following notice is reproduced from the upstream `LICENSE` in satisfaction of
the MIT license's condition that the copyright notice and permission notice be
included in all copies or substantial portions of the Software:

```
MIT License

Copyright (c) 2020-2026 Pawel Kuna

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Bundled in the Windows release

The Windows download of Postboy Advance is one folder, `Postboy Advance`. It holds
the program and, in `_internal`, the runtime the program needs. The components
below are redistributed in that folder unmodified. Their full licence texts travel
in the folder's `licenses` directory, which is copied from
[`packaging/licenses`](packaging/licenses).

### Qt 6 - LGPL-3.0-only

- **Upstream:** <https://www.qt.io/>
- **Version:** 6.11.2, from the PySide6 6.11.2 wheels
- **Upstream license:** `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`, the
  `License` field of the installed PySide6 distributions. This release uses Qt
  under LGPL-3.0-only.
- **Shipped files:** `_internal/PySide6/Qt6*.dll` and the plugins under
  `_internal/PySide6/plugins`
- **License texts shipped:** `licenses/LGPL-3.0.txt`, and `licenses/GPL-3.0.txt`,
  whose terms the LGPL incorporates

The Qt libraries ship as separate, replaceable DLLs in the `_internal` folder; the
program loads them at run time and is not statically linked against them, so you
can swap in your own build of the same Qt version. The source for this version is
at <https://download.qt.io/official_releases/qt/6.11/6.11.2/> and
<https://code.qt.io/>.

### PySide6 and Shiboken6 - LGPL-3.0-only

- **Upstream:** <https://pyside.org>
- **Version:** 6.11.2
- **Upstream license:** `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`, the
  `License` field of the installed `PySide6`, `PySide6_Essentials` and `shiboken6`
  distributions. This release uses them under LGPL-3.0-only.
- **Shipped files:** `_internal/PySide6/*.pyd`, `_internal/PySide6/pyside6.abi3.dll`
  and `_internal/shiboken6`
- **License texts shipped:** `licenses/LGPL-3.0.txt` and `licenses/GPL-3.0.txt`

Like Qt, these are separate, replaceable files in the `_internal` folder. The
source is at
<https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/>
and <https://code.qt.io/cgit/pyside/pyside-setup.git/>.

### Python - PSF-2.0

- **Upstream:** <https://www.python.org/>
- **Version:** 3.12.10, the Windows build from python.org
- **Upstream license:** the Python Software Foundation License Version 2, in that
  build's `LICENSE.txt`
- **Shipped files:** `_internal/python312.dll`, `_internal/python3.dll`, the
  extension modules `_internal/*.pyd`, `_internal/base_library.zip` and the
  standard-library modules inside the program
- **License text shipped:** `licenses/Python-LICENSE.txt`, a copy of that build's
  `LICENSE.txt`

The Python build carries a few C libraries of its own. Their terms are in
`licenses/Python-LICENSE.txt` or reproduced below, both taken from that Python
installation's licence file and its documentation page "Licenses and
Acknowledgements for Incorporated Software":

| Library | Where it is | Terms |
| --- | --- | --- |
| OpenSSL 3.0.16 | `_internal/libcrypto-3.dll`, used by `_hashlib.pyd` | Apache License 2.0, full text in `licenses/Python-LICENSE.txt` |
| bzip2 1.0.8 | `_internal/_bz2.pyd` | the bzip2 licence, in `licenses/Python-LICENSE.txt` |
| zlib | built into `_internal/python312.dll` | the zlib licence, below |
| libmpdec | `_internal/_decimal.pyd` | the libmpdec licence, below |

```
Copyright (C) 1995-2011 Jean-loup Gailly and Mark Adler

This software is provided 'as-is', without any express or implied
warranty.  In no event will the authors be held liable for any damages
arising from the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software. If you use this software
   in a product, an acknowledgment in the product documentation would be
   appreciated but is not required.

2. Altered source versions must be plainly marked as such, and must not be
   misrepresented as being the original software.

3. This notice may not be removed or altered from any source distribution.

Jean-loup Gailly        Mark Adler
jloup@gzip.org          madler@alumni.caltech.edu
```

```
Copyright (c) 2008-2020 Stefan Krah. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
SUCH DAMAGE.
```

### PyYAML - MIT

- **Upstream:** <https://pyyaml.org/>
- **Version:** 6.0.3
- **Upstream license:** MIT, the `License` field of the installed distribution and
  its `LICENSE` file
- **Shipped files:** `_internal/yaml/_yaml.cp312-win_amd64.pyd` and the `yaml`
  modules inside the program
- **License text shipped:** `licenses/PyYAML-LICENSE.txt`

### PyInstaller bootloader - GPL-2.0-or-later with the Bootloader Exception

- **Upstream:** <https://pyinstaller.org/>
- **Version:** 6.22.3
- **Upstream license:** GPL-2.0-or-later with the Bootloader Exception, stated in
  the installed distribution's `COPYING.txt`. The run-time hooks PyInstaller
  embeds are Apache-2.0, stated in the same file.
- **Shipped files:** the start-up code inside `Postboy Advance.exe`
- **License text shipped:** `licenses/PyInstaller-COPYING.txt`, which holds the
  GPL-2.0 text, the exception and the Apache-2.0 text

The Bootloader Exception lets a program frozen with PyInstaller be distributed
under any licence, so the exception, not the GPL, governs how this program is
shipped.

### Microsoft Visual C++ and Universal C runtime

- **Shipped files:** `VCRUNTIME140.dll`, `VCRUNTIME140_1.dll`, `MSVCP140.dll`,
  `MSVCP140_1.dll`, `MSVCP140_2.dll`, `ucrtbase.dll` and the `api-ms-win-*.dll`
  forwarders, in `_internal`, `_internal/PySide6` and `_internal/shiboken6`
- **License:** not open source. Microsoft lets developers redistribute these files
  with their programs as distributable code. The conditions Python's Windows build
  states for that code are in `licenses/Python-LICENSE.txt`, under "Additional
  Conditions for this Windows binary build".

---

## Game content

This repository contains no commercial ROMs, BIOS images, saves, states, memory
dumps, or extracted proprietary game assets, and none have ever been committed.
The Dragon Ball Z games and all of their content remain the property of their
respective rights holders; this project is unaffiliated with them. Supply only
game images you are legally entitled to use.
