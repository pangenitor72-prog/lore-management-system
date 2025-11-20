# Master Agent Guide

This guide is specifically for AI collaborators working within the Lore Management System (LMS) repository. It outlines the expected workflow, rules of engagement, and best practices to ensure smooth, efficient, and high-quality contributions.

## 1. Which Files to Read First

To quickly orient yourself within the codebase, prioritize reading the following documents and files:

-   **`docs/engineering/ARCHITECTURE_OVERVIEW.md`**: High-level understanding of the system's structure and data flow.
-   **`docs/engineering/PROJECT_CONVENTIONS.md`**: Essential for understanding coding style, naming, and structural expectations.
-   **`docs/engineering/REPO_RULES.md`**: Non-negotiable rules for Git workflow, testing, and what *not* to touch.
-   **`src/api.py`**: The main FastAPI application entry point, providing an overview of exposed endpoints.
-   **`src/models.py`**: Defines all Pydantic models and Enums, which are crucial for understanding data structures.
-   **`src/database.py`**: Explains how database connections are managed and operations are performed.

## 2. How to Propose Changes

Follow a structured approach for all proposed changes:

1.  **Understand the Request:** Ensure a complete understanding of the user's objective, including any constraints or specific requirements.
2.  **Formulate a Plan:** Develop a concise, step-by-step plan before initiating any work. This plan should detail:
    *   Affected files and components.
    *   Specific audit points being addressed (if applicable).
    *   Implementation strategy (e.g., refactoring steps, new feature breakdown).
    *   Testing strategy (how will the changes be verified?).
3.  **Use `write_todos`:** For complex tasks, break them down into smaller subtasks and use the `write_todos` tool to track progress. Update the status (`pending`, `in_progress`, `completed`, `cancelled`) diligently.
4.  **Seek Approval:** Present your plan (or significant changes to it) to the human user for approval *before* making any file modifications.

## 3. Required Steps During Implementation

-   **Adhere to Conventions:** Strictly follow `docs/engineering/PROJECT_CONVENTIONS.md`.
-   **Respect Repository Rules:** Abide by `docs/engineering/REPO_RULES.md` (e.g., use feature branches, write tests).
-   **Explain Critical Commands:** Before executing any `run_shell_command` that modifies the file system or state, provide a brief explanation of its purpose and potential impact.
-   **Show Diffs for All Changes:** After every logical change to the codebase (e.g., fixing one audit point, implementing a small part of a feature), use `git diff` or `git diff --staged` and present the diff to the user for review. Wait for explicit approval before proceeding to the next logical change.
-   **Iterative Development:** Work in small, coherent steps. This makes reviews easier and reduces the risk of large, complex changes.
-   **Prioritize Safety and Idempotence:** Ensure all operations are safe and, where appropriate, idempotent.

## 4. How to Respect `PROJECT_CONVENTIONS` and `REPO_RULES`

-   **Read and Internalize:** Regularly review `PROJECT_CONVENTIONS.md` and `REPO_RULES.md`.
-   **Self-Correction:** If you identify a deviation from these rules in your own generated code, proactively correct it.
-   **Consistency over Preference:** Always prioritize project-established conventions over personal or generalized coding preferences.
-   **Question Ambiguity:** If a convention is unclear or a rule seems to conflict with the current task, ask the human user for clarification.

## 5. How to Log Your Work in the Changelog

-   **`docs/engineering/CHANGELOG_AI.md`:** All significant actions taken by an AI agent must be logged here.
-   **Format:** Each entry should include:
    -   **Date:** (e.g., `YYYY-MM-DD`)
    -   **Branch Name:** The feature branch where the work occurred.
    -   **Summary:** A concise description of the changes made, referencing audit points (C#, M#) or new features.
    -   **Diff (Optional but Recommended):** A link or reference to the specific diff if it's too large to include inline.
-   **Granularity:** Log major milestones or completed tasks, not every single `replace` operation. For example, "Implemented C1 and C3 fixes across `api.py` and `database.py`" is appropriate.

## 6. Verification and Finalization

-   **Run Tests:** After completing changes, run the test suite (`pytest`) to ensure no regressions were introduced and new tests pass.
-   **Linter/Type Checker:** Run any project-specific linting (`flake8`, `ruff`) or type-checking (`mypy`) tools.
-   **Final Diff and Commit:** Present a final summarized diff for approval, and then commit with a clear, professional message.
-   **Do NOT Push Automatically:** Never push changes to a remote repository unless explicitly instructed by the user.
