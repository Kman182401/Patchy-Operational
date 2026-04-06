---
name: deploy-checklist
description: >
  This skill should be used when the user asks to "deploy checklist", "pre-deploy review", "ready to ship", "release checklist", "deployment plan", "go/no-go", "pre-release review", "production readiness", "canary deploy plan", "rollback plan", or any request to verify readiness before deploying a change to production. Also trigger when preparing to deploy, release, or ship code.
---

# Deployment Checklist

Generate a customized pre-deployment checklist based on what's being deployed and the risk level.

## Gather Context

Before generating the checklist, determine:

1. **What's changing?** — New feature, bug fix, dependency update, infrastructure change, database migration, config change.
2. **Risk level** — Low (copy change, feature flag), Medium (new endpoint, schema change), High (auth changes, payment flow, data migration).
3. **Deploy process** — CI/CD auto-deploy, manual deploy, canary, blue-green, feature flag rollout.

If the user doesn't specify, ask. A config change and a database migration need very different checklists.

## Checklist Template

Adapt this based on context — remove sections that don't apply, add specifics for the actual change.

### Pre-Deploy

- [ ] **Code reviewed and approved** — PR has required approvals
- [ ] **Tests passing** — Unit, integration, and E2E tests green in CI
- [ ] **No unrelated changes** — PR is scoped to the stated purpose
- [ ] **Environment variables** — Any new env vars are set in staging and production
- [ ] **Database migrations** — Tested, reversible, and backward-compatible with current code
- [ ] **Feature flags** — New functionality behind a flag if applicable
- [ ] **Documentation updated** — API docs, runbooks, README if user-facing changes

### Deploy

- [ ] **Deploy to staging first** — Verify in a non-production environment
- [ ] **Smoke test staging** — Hit critical paths manually or with automated checks
- [ ] **Deploy to production** — Follow the standard deploy process
- [ ] **Canary period** — If available, monitor canary before full rollout

### Post-Deploy

- [ ] **Smoke test production** — Verify the change works in prod
- [ ] **Monitor metrics** — Error rates, latency, CPU/memory for 15-30 minutes
- [ ] **Monitor logs** — Watch for new exceptions or warnings
- [ ] **Verify alerts** — Confirm monitoring and alerting are active
- [ ] **Communicate** — Notify the team in the deploy channel

### Rollback Plan

- [ ] **Rollback command ready** — Know exactly how to revert
- [ ] **Rollback tested** — Verified the rollback procedure works
- [ ] **Rollback criteria** — Define what triggers a rollback (error rate > X%, latency > Yms)
- [ ] **Data rollback** — If migrations ran, know how to reverse them

## Risk-Specific Additions

**Database migrations:** Add backward-compatibility verification, migration dry-run, backup confirmation.

**Auth/security changes:** Add penetration test or security review, session handling verification, permission matrix check.

**Payment/billing:** Add sandbox transaction test, idempotency verification, reconciliation check.

**Infrastructure:** Add capacity planning review, DNS propagation check, certificate verification.

## Output

Present as a clean, copy-pasteable checklist with the irrelevant sections removed and risk-specific items added. Include a one-line rollback command if the user shares their deploy tooling.
