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

## 2. Continuous Git Version Control & Commit Discipline
- Always track all code and documentation changes in Git continuously.
- Do not accumulate massive uncommitted working tree diffs. Commit logical units of work promptly with clear Conventional Commits messages (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`).
- Always ensure git working directory is clean after completing tasks.

## 3. Dual-Repository Documentation Synchronization
Whenever documentation, guides, release notes, catalog manifests, or architecture docs are updated:
- Synchronize and update documentation across **both** repositories:
  1. `PyBionic` (`c:\Users\User\OneDrive\Desktop\Bot` / `https://github.com/nasibullo03/PyBionic.git`)
  2. `PyBionic-Hub` (`C:\Users\User\PyBionic-Hub-Staging` / `https://github.com/nasibullo03/PyBionic-Hub.git`)
- Ensure consistency in version badges, feature descriptions, catalog entries, and localized translations across both repositories.

## 4. Custom Productivity & Automation Tooling
To maximize agent speed, autonomy, and reduce repetitive manual cycles:
- You are explicitly encouraged and permitted to write dedicated helper scripts, CLI utilities, and automation tools inside the workspace (e.g. in `tools/` or `scripts/`).
- **High-Velocity Android Testing & Inspection:**
  - Create Python or PowerShell scripts for batch-capturing screenshots across screen transitions during ADB test workflows.
  - Automate UI hierarchy dumps (`uiautomator dump`) and instant parsing to eliminate slow manual inspection.
  - Implement real-time logcat streaming filters for crash detection and bot runtime events.
- **Static Analysis & Fast Code Verification:**
  - Develop custom AST validators, template checkers, or quick runners to test components without waiting for heavyweight builds when not needed.
- **Host Safety Constraint:** All automation scripts must remain strictly isolated to the project directory, execute safely, and never harm the user's host OS or external systems.

## 5. Android Device & Build Guidelines
- DO NOT execute `assembleRelease` without explicit user permission.
- Testing on the physical Android device or emulator must be executed **strictly upon user request**.
- Always verify changes on the physical device or emulator when connected via ADB.
- Keep UI strictly compliant with Android edge-to-edge system bars (proper status bar and navigation bar insets).
