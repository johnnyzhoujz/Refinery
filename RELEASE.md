# Release Process

## Pre-release checklist
- [ ] `pytest` passes locally and in CI.
- [ ] Version bumped in `pyproject.toml`, `refinery/__init__.py`, `refinery/cli.py`.
- [ ] `CHANGELOG.md` updated with release date.
- [ ] README install instructions reflect new version/package name.
- [ ] Example traces validated (sanitization commands pass).
- [ ] Dist artifacts contain `examples/` and `schema/`.

## Steps
1. `git checkout -b release/vX.Y.Z`
2. Update versions & changelog; run `python -m build && twine check dist/*`
3. Smoke test in a clean venv.
4. `git add . && git commit -m "Release vX.Y.Z"`
5. `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
6. `git push origin release/vX.Y.Z && git push origin vX.Y.Z`
7. Create GitHub Release (paste changelog, upload artifacts).
8. `twine upload dist/*`
9. Verify: `pip install refinery-cli==X.Y.Z && refinery --version`.
10. Announce (X/Twitter, Hacker News, r/LangChain, LangChain Discord).

## Post-release
- Merge `release/vX.Y.Z` into `main`.
- Reopen `[Unreleased]` section in changelog.
- Create milestone for next version; seed roadmap issues.
