# Repository Rules (for Humans and AIs)

These rules govern all work performed within this Lore Management System (LMS) repository. Adherence is mandatory for maintaining code quality, ensuring stability, and facilitating collaborative development.

## 1. Branching Strategy

- **Never write directly to `main`:** All changes, no matter how small, must originate from a dedicated feature branch.
- **Feature Branch Naming:** Use descriptive names, e.g., `feature/add-new-entity-type`, `bugfix/issue-123-login-error`, `refactor/db-connection-handling`.
- **Keep Branches Focused:** Each branch should address a single feature, bug fix, or logical refactoring unit.
- **Regular Rebase/Merge:** Keep your feature branch up-to-date with `main` to avoid large merge conflicts. Prefer rebasing for clean history if working on a personal branch, otherwise merge from `main` frequently.

## 2. Code Review and Approval

- **Mandatory Reviews:** All code changes must be submitted for review via a Pull Request (PR) and approved by at least one other engineer (or the designated lead) before merging into `main`.
- **Clear PR Descriptions:** PRs must include a clear summary of changes, motivation, relevant issue trackers, and steps to test.
- **Address Feedback:** All review comments must be addressed, either by implementing changes or providing a clear justification for not doing so.

## 3. Testing Requirements

- **Run Tests Locally:** Before pushing your branch and opening a PR, all existing unit and integration tests must pass locally (`pytest`).
- **New Features/Bug Fixes Require New Tests:**
    - For new features, add corresponding unit and/or integration tests to cover the new functionality.
    - For bug fixes, add a regression test that fails before the fix and passes after it.
- **Aim for High Coverage:** Strive to maintain or increase test coverage for modified or new code.
- **Test Isolation:** Tests should be isolated, deterministic, and not depend on external services or production data. Use in-memory databases or mocking where appropriate.

## 4. Documentation

- **Self-Documenting Code:** Write clear, concise, and self-documenting code. Use meaningful variable names, function names, and class names.
- **Docstrings:** All public functions, methods, and classes must have informative docstrings (using Google-style or reStructuredText format) explaining their purpose, arguments, and return values.
- **Update Engineering Documentation:** If your changes impact architecture, conventions, or guidelines, update the relevant documents in `docs/engineering/`.
- **Changelog Entries:** For significant changes, add an entry to `docs/engineering/CHANGELOG_AI.md` (for AI agents) or the main project changelog (for humans).

## 5. What is Off-Limits (Do Not Touch)

- **`.env` files:** Never commit `.env` files or hardcode sensitive information (API keys, credentials, etc.) directly into the codebase. Use environment variables.
- **Database Files (`.db`):** Never commit SQLite database files (e.g., `data/lore.db`) to version control. The schema (`schema.sql`) is version controlled, but the data is not.
- **Renaming Modules/Public Endpoints:** Do not rename core modules (`src/api.py`, `src/models.py`, `src/database.py`) or public-facing API endpoints without explicit, prior approval and a clear migration strategy.
- **Breaking DB Schema Changes:** Avoid making breaking changes to the database schema (`schema.sql`) without a clear migration guide and communication.
- **Vendor Directories:** Do not modify or commit files within automatically generated vendor directories (e.g., `venv/`, `__pycache__/`, `.pytest_cache/`).

## 6. Commit Messages

- **Clear and Concise:** Write commit messages that are clear, concise, and provide sufficient context.
- **Focus on "Why":** Explain the *reason* for a change, not just *what* was changed.
- **Conventional Commits (Recommended):** Consider using conventional commit messages (e.g., `feat: add new user authentication`, `fix: resolve N+1 query issue in entity list`).

By adhering to these rules, we ensure a stable, secure, and collaborative development environment for the LMS.
