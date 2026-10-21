# Contributing to Opal

Thanks for wanting to help. Opal is a small, careful codebase and the bar
for a change is that it works on three operating systems and still works with
the network unplugged.

## Before you start

- **Open an issue first** for anything larger than a bug fix or a
  documentation correction. It saves everyone time to agree on the approach
  before you write the code.
- **Check the roadmap** in the README. If the thing you want is already
  listed, say so in the issue — it may already be planned, and discussion is
  more useful than a patch that will not be merged.

## Setting up

```bash
git clone https://github.com/gaurav-eshanura/opal.git
cd opal
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
```

Opal targets Python 3.10 and newer.

## Running the tests

```bash
python test_opal.py                   # the core suites
python test_opal.py --full            # adds the slow real-media suites
python tests/test_every_feature.py   # the exhaustive 165-check audit
```

Please run at least `python test_opal.py` before opening a pull request, and
`--full` if your change touches conversion, media or the PDF engine.

A change is not done until the suite is green. If you find a genuine bug
while working, please report it as a separate issue rather than fixing it
silently inside your feature.

## Code style

- Follow the style of the file you are in. The project does not use a
  linter, and consistency with the surrounding code matters more than any
  particular style.
- Keep the platform layer intact. If your change needs the operating
  system, add it to `opal_studio/platform_compat.py` rather than calling
  `ctypes`, the registry or a shell from a feature module. The test suite
  checks that nothing outside that file touches the OS directly.
- Keep the network layer intact. Downloads go through the allow-listed,
  IP-pinned fetcher in `opal_studio/engines.py`. Do not add a second way to
  reach the network.
- New user-visible strings need both an English and a Hinglish version on
  the website (`data-en` and `data-hing`).
- New colours belong in `opal_studio/theme.py` or `opal_studio/glass.py`,
  not inline in a widget.

## What we will not accept

- Anything that uploads a user's file, in whole or in part.
- Anything that adds a dependency without a good reason. The portable build
  is 202 MB and every megabyte is defended.
- A change that only works on one operating system.
- Advertising, tracking or analytics of any kind.

## Commit messages and pull requests

- One logical change per pull request.
- Describe **why** in the pull request body, not only what. The diff already
  shows what.
- Add a line to `CHANGELOG.md` under *Unreleased*.

## Reporting bugs

A good report includes your operating system and version, the Opal version,
what you did, what you expected, what happened, and a sample file if you can
share one without exposing anything private.

## Code of conduct

Be decent to each other. Assume good faith, keep discussion focused on the
work, and treat people with respect. Harassment of any kind is not
tolerated.
