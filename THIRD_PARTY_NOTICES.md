# Third-party content notices

The project keeps imported or adapted puzzle data separate from application
code.  When larger external catalogs are enabled, keep this file and the
upstream license text with distributions.

## Chinese poetry catalog

- Reference project: [chinese-poetry/chinese-poetry](https://github.com/chinese-poetry/chinese-poetry)
- Upstream license: MIT
- Fixed source version: `chinese-poetry` npm package `2.0.1`
- Use in this repository: `backend/data/poetry_bank.json` is a transformed,
  simplified-Chinese subset of the upstream 唐诗三百首、宋词三百首、千家诗、
  诗经、纳兰性德诗集 and 曹操诗集 files. It stores 1445 normalized works
  and is merged with 38 manually curated public-domain works at runtime.
  Input SHA-256 values are preserved in the generated file metadata. The reproducible transform is
  `backend/scripts/build_poetry_bank.py`.

Upstream copyright and license notice:

```text
The MIT License (MIT)

Copyright (c) 2016 JackeyGao

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

## Sokoban / Boxoban

- Reference project: [google-deepmind/boxoban-levels](https://github.com/google-deepmind/boxoban-levels)
- Upstream license: Apache License 2.0
- Use in this repository: the board encoding follows the documented Sokoban
  symbols.  Current playable boards are generated deterministically by this
  project; no upstream level file is bundled yet.  The service boundary allows
  a curated Boxoban import to replace generated boards later.

## Arrow Maze

- Reference project: [MiniMax-AI/SynLogic](https://github.com/MiniMax-AI/SynLogic)
- Upstream license: MIT
- Use in this repository: SynLogic informed the choice of an arrow-based logic
  game and deterministic verification.  The mini-program uses a touch-friendly
  jump-along-the-arrow ruleset implemented independently in
  `backend/extra_puzzles.py`; it does not copy SynLogic's training dataset.
