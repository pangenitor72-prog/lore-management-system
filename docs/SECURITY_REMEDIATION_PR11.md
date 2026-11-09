# Credential exposure remediation (PR #11 follow-up)

## Summary

The closed, unmerged PR #11 identified real-looking credentials in `.env.production.template`. The current default branch still contained these values, and a tracked text file under `docs/tokens/` held a GitHub-token-like value. A deployment setup script also contained embedded credential literals.

This remediation branch is deliberately narrow: it replaces template credentials with placeholders, removes embedded setup-script values, untracks the token file, broadens ignore rules, and rejects missing Neo4j credentials in the driver adapter. In production, the application refuses to start with a missing Neo4j URI or password. Existing development-mode degraded startup behavior remains.

## Required owner actions (NOT performed by this PR)

1. **Revoke the exposed GitHub token now** in GitHub settings, whether or not it is still in use. Inspect recent token usage and repository audit activity for unauthorized actions.
2. **Rotate the Neo4j password** for any relevant local or Aura instance and update the applicable deployment secret/configuration. Confirm which Neo4j instance is actually active before changing credentials.
3. **Replace the application API secret and embedding API credential** wherever those old values may still be accepted. If a key is not real or was never activated, record that determination.
4. Check other clones, forks, deployment copies, logs, caches, and CI artifacts for exposed values. Investigate suspicious activity and preserve incident evidence.
5. Verify startup, database connection, relevant application tests, and deployment in a controlled environment after rotation. **No deployment or secret rotation is part of this change.**

## Important limitations

- Deleting a tracked file or replacing its contents **does not erase earlier commits** or the closed PR's quoted values. The repository is public; treat exposed secrets as compromised even if history is later rewritten.
- This PR does **not** rewrite Git history, force-push, merge, rotate any credentials, or change hosting configuration.
- `.gitignore` prevents accidental new additions but cannot protect previously tracked files.
- Placeholder values must be replaced locally or in a secret manager, never committed.
- Startup and test validation are proposed, not evidence that a live production deployment was exercised.

## Review checklist

- [ ] Confirm template and setup script contain no real credentials
- [ ] Confirm tracked token file is absent from this branch
- [ ] Run unit and integration tests in the project environment
- [ ] Verify local/offline and production startup behavior
- [ ] Confirm no unanticipated deployment workflow ran
- [ ] Complete credential rotation and incident investigation separately
