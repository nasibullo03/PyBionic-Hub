# PyBionic Project Rules & Guidelines

## 1. SemVer (Semantic Versioning) Policy
All releases and code updates must strictly adhere to Semantic Versioning (SemVer 2.0.0):
Format: `MAJOR.MINOR.PATCH` in `version.properties`.

- **MAJOR** (`major`): Incremented when incompatible changes are introduced (breaking backward compatibility in runtime, project structure, or APIs).
- **MINOR** (`minor`): Incremented when new features, templates, or capabilities are added in a backward-compatible manner.
- **PATCH** (`patch`): Incremented when bug fixes, visual adjustments, UI/UX polish, or security patches are applied without changing existing behavior.
- **BUILD** (`build`): Incremented with each release or patch so that Android's monotonic `versionCode` increases (`versionCode = major * 10000 + minor * 100 + build`).

Whenever changes are made:
1. Update `version.properties`.
2. Update `RELEASE_NOTES.md` and badges in `README.md`.
3. Ensure all unit tests pass before committing.
4. Create a corresponding Git release tag (`vMAJOR.MINOR.PATCH`).

## 2. Android Device & Build Guidelines
- DO NOT execute `assembleRelease` without explicit user permission.
- Always verify changes on the physical device or emulator when connected via ADB.
- Keep UI strictly compliant with Android edge-to-edge system bars (proper status bar and navigation bar insets).
