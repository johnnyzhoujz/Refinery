# Release Process

This document describes the repeatable process for releasing new versions of Refinery.

## Version Numbering

Refinery follows [Semantic Versioning](https://semver.org/):

- **MAJOR** (v1.0.0): Breaking changes, incompatible API changes
- **MINOR** (v0.1.0): New features, backwards compatible
- **PATCH** (v0.1.1): Bug fixes, backwards compatible

## Pre-Release Checklist

Before starting a release, ensure:

- [ ] All tests passing (`pytest tests/`)
- [ ] CI green on main branch
- [ ] All planned features/fixes merged
- [ ] Documentation updated for new features
- [ ] CHANGELOG.md reviewed and ready
- [ ] No known critical bugs
- [ ] Example traces sanitized and documented
- [ ] Security review completed (if applicable)

## Version Bump Locations

When releasing, update version in **THREE** locations:

### 1. pyproject.toml

```toml
[project]
name = "refinery-cli"
version = "X.Y.Z"  # Update this line
```

### 2. refinery/__init__.py

```python
__version__ = "X.Y.Z"  # Update this line
```

### 3. refinery/cli.py

```python
def print_version(ctx, param, value):
    if value:
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        console.print(f"Refinery vX.Y.Z (GPT-5, Python {python_version})")  # Update vX.Y.Z
        ctx.exit()
```

**Critical**: All three locations MUST have the same version number.

## Release Steps

### 1. Create Release Branch

```bash
git checkout main
git pull origin main
git checkout -b release/vX.Y.Z
```

### 2. Update Version Numbers

Update all three locations listed above with the new version number.

```bash
# Edit files
vim pyproject.toml
vim refinery/__init__.py
vim refinery/cli.py

# Verify changes
grep -n "version" pyproject.toml
grep -n "__version__" refinery/__init__.py
grep -n "Refinery v" refinery/cli.py
```

### 3. Update CHANGELOG.md

Replace `[Unreleased]` header with release version and date:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- Feature 1
- Feature 2

### Fixed
- Bug fix 1

### Changed
- Change 1
```

Add new `[Unreleased]` section at top:

```markdown
## [Unreleased]

### Planned for vX.Y+1
- Future feature 1
```

### 4. Verify Documentation

Check that all documentation is current:

```bash
# Verify README has correct install command
grep "pip install refinery-cli" README.md

# Check examples work
refinery chat --trace-file examples/demo_trace.json

# Verify version command
refinery --version
# Should show: Refinery vX.Y.Z (GPT-5, Python 3.X)
```

### 5. Build and Check Package

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build package
python -m build

# Check package contents
twine check dist/*

# Verify critical files are included
tar -tzf dist/refinery-cli-X.Y.Z.tar.gz | grep examples/demo_trace.json
tar -tzf dist/refinery-cli-X.Y.Z.tar.gz | grep -E "(README|LICENSE|CHANGELOG)"

# If schema files exist, verify they're included too
tar -tzf dist/refinery-cli-X.Y.Z.tar.gz | grep schema/
```

### 6. Test Installation in Clean Environment

```bash
# Create fresh virtual environment
python -m venv test-venv
source test-venv/bin/activate  # On Windows: test-venv\Scripts\activate

# Install from built package
pip install dist/refinery_cli-X.Y.Z-py3-none-any.whl

# Verify installation
refinery --version
refinery chat --help

# Test with example trace
refinery chat --trace-file examples/demo_trace.json

# Clean up
deactivate
rm -rf test-venv
```

### 7. Commit and Tag

```bash
# Commit version bump
git add pyproject.toml refinery/__init__.py refinery/cli.py CHANGELOG.md
git commit -m "Release vX.Y.Z"

# Create annotated tag
git tag -a vX.Y.Z -m "Release vX.Y.Z"

# Verify tag
git show vX.Y.Z
```

### 8. Push to Repository

```bash
# Push branch
git push origin release/vX.Y.Z

# Push tag
git push origin vX.Y.Z
```

### 9. Create GitHub Release

1. Go to https://github.com/your-org/refinery/releases/new
2. Select tag: `vX.Y.Z`
3. Release title: `Refinery vX.Y.Z`
4. Description: Copy from CHANGELOG.md for this version
5. Attach built distributions (optional):
   - `dist/refinery-cli-X.Y.Z.tar.gz`
   - `dist/refinery_cli-X.Y.Z-py3-none-any.whl`
6. Click "Publish release"

### 10. Publish to PyPI

**Production release:**

```bash
# Publish to PyPI (IRREVERSIBLE!)
twine upload dist/*

# Enter PyPI credentials when prompted
# Username: __token__
# Password: pypi-xxxxxxxxxxxxx
```

**Test release first (recommended):**

```bash
# Upload to Test PyPI first
twine upload --repository testpypi dist/*

# Test installation from Test PyPI
pip install --index-url https://test.pypi.org/simple/ refinery-cli

# If everything works, upload to production PyPI
twine upload dist/*
```

### 11. Verify PyPI Release

```bash
# Wait 1-2 minutes for PyPI to update
sleep 120

# Install from PyPI in clean environment
python -m venv verify-venv
source verify-venv/bin/activate

pip install refinery-cli
refinery --version

# Should show: Refinery vX.Y.Z (GPT-5, Python 3.X)

deactivate
rm -rf verify-venv
```

### 12. Merge Release Branch

```bash
# Create pull request for release branch
gh pr create --title "Release vX.Y.Z" --body "Release version X.Y.Z"

# After PR approval, merge to main
git checkout main
git pull origin main

# Verify tag is on main
git log --oneline --decorate | head -5
```

### 13. Announce Release

**GitHub Discussions:**
- Post announcement in Discussions with release highlights

**Social Media:**
- Twitter/X: Share release with key features
- LinkedIn: Professional announcement
- Reddit: r/Python, r/MachineLearning (if appropriate)

**Example announcement:**
```
Refinery vX.Y.Z is now available!

New in this release:
- Feature 1: Description
- Feature 2: Description
- Bug fix: Description

Install: pip install refinery-cli

Read more: https://github.com/your-org/refinery/releases/tag/vX.Y.Z
```

## Post-Release

### Update Main Branch

Ensure main branch has the release:

```bash
git checkout main
git pull origin main
git log --oneline | head -5
```

### Monitor for Issues

- Watch GitHub Issues for new reports
- Monitor PyPI download stats
- Check CI/CD for any failures

### Plan Next Release

Create milestone for next version:

```bash
# On GitHub:
# 1. Go to Issues → Milestones
# 2. Create new milestone: vX.Y+1.Z
# 3. Add planned features/fixes to milestone
```

## Hotfix Process

For urgent bug fixes between releases:

### 1. Create Hotfix Branch

```bash
git checkout vX.Y.Z  # Check out latest release tag
git checkout -b hotfix/vX.Y.Z+1
```

### 2. Apply Fix

```bash
# Make changes
vim refinery/module.py

# Test thoroughly
pytest tests/

# Commit
git commit -m "Fix: Description of bug fix"
```

### 3. Bump Patch Version

Update version in all three locations (increment patch number only).

### 4. Follow Release Steps

Continue with steps 4-13 from the main release process.

### 5. Backport to Main

```bash
# Cherry-pick fix to main branch
git checkout main
git cherry-pick <hotfix-commit-sha>
git push origin main
```

## Rollback Process

If a release has critical issues:

### 1. Yank from PyPI

```bash
# Yank the bad release (doesn't delete, just hides)
# This requires PyPI account with permissions
# Go to: https://pypi.org/manage/project/refinery-cli/releases/
# Click on version → "Options" → "Yank release"
```

### 2. Publish Hotfix

Follow the hotfix process to release a fixed version.

### 3. Communicate

- Update GitHub Release notes with "YANKED" label
- Post in Discussions about the issue
- Recommend users upgrade to hotfix version

## Checklist Summary

Quick checklist for releases:

- [ ] Tests pass, CI green
- [ ] Version bumped in 3 locations
- [ ] CHANGELOG.md updated
- [ ] Documentation current
- [ ] Package built and checked
- [ ] Clean install tested
- [ ] Committed and tagged
- [ ] GitHub release created
- [ ] Published to PyPI
- [ ] Installation verified
- [ ] Release branch merged
- [ ] Announcement posted

## Troubleshooting

### Build Fails

```bash
# Clean and rebuild
rm -rf dist/ build/ *.egg-info
python -m build
```

### PyPI Upload Fails

```bash
# Check credentials
cat ~/.pypirc

# Verify package
twine check dist/*

# Try Test PyPI first
twine upload --repository testpypi dist/*
```

### Version Mismatch

```bash
# Find all version references
grep -r "0\.1\.0" . --include="*.py" --include="*.toml"

# Update missed locations
```

### Tag Already Exists

```bash
# Delete local tag
git tag -d vX.Y.Z

# Delete remote tag (careful!)
git push origin :refs/tags/vX.Y.Z

# Recreate tag
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

## Questions?

If you have questions about the release process:

- Check existing releases: https://github.com/your-org/refinery/releases
- See CONTRIBUTING.md for development workflow
- Open a GitHub Discussion for process questions
