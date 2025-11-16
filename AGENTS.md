# Repository Guidelines

## Project Structure & Module Organization
AutoDefineAddon/ hosts the actual Anki add-on: `autodefine.py` drives hooks,
`oxford.py` handles scraping, subfolders like `modules/` and `webbrowser/`
wrap helper logic, and `images/` holds shipped icons. Use `config.json`
alongside `config.md` when introducing new options so UI defaults and
documentation stay aligned. The `tests/` folder stores pytest scenarios,
fixtures (e.g., `tests.py`), deck data, and `test_data.txt`; keep new fixtures
small so repository size remains manageable. Packaging helpers live under
`scripts/` (notably `build_addon.sh`) and GitHub workflow definitions in
`.github/workflows/` mirror the same steps to ensure the uploadable bundle
matches what ships from CI.

## Build, Test, and Development Commands
Run `bash scripts/build_addon.sh` from the repo root to produce
`dist/AutoDefineAddon.zip`; the script wipes `build/`, strips `__pycache__`,
and mirrors the CI workflow. Execute `pytest tests/tests.py` (requires
`pytest-anki`, Anki, and Requests) to replay the sample deck end-to-end; add
`-k <pattern>` for targeted runs. While iterating inside Anki, symlink
`AutoDefineAddon/` into your add-ons folder and restart Anki after edits to
reload hooks.

## Coding Style & Naming Conventions
Follow standard Python 3 practices with 4-space indents, `snake_case` for
functions/modules, and UPPER_CASE for config constants to match
`autodefine.py`. Keep imports grouped (stdlib, third-party, Anki) and prefer
explicit `from aqt import …` usage already in place. Apply type hints where
public hooks or helpers surface (`Optional[AddCards]`, etc.) and document any
new config section inside `config.md`. Never commit generated files such as
`meta.json`, `__pycache__`, or build/zip artifacts; the build script already
strips them.

## Testing Guidelines
Tests rely on pytest parametrization plus `pytest-anki` to spin up an
isolated profile; replicate the pattern in `tests/tests.py`. Set `"TEST_MODE":
true` in configs for deterministic scraping, and extend `test_data.txt` only
when the scenario list materially changes. When adding coverage, assert that
affected note fields change (definition/audio/phonetics) instead of
re-mocking dialogs so regressions stay visible.

## Commit & Pull Request Guidelines
Git history favors concise subjects such as "Altered create symlink script".
Keep commit titles imperative, under ~72 characters, and reference linked
issues (for example, `Fix #123`). Pull requests should describe user impact,
outline manual verification (Anki version, shortcut, deck type), and attach
screenshots or GIFs for UI changes. Confirm the workflow artifact
`dist/AutoDefineAddon.zip` downloads and installs cleanly before requesting
review.
