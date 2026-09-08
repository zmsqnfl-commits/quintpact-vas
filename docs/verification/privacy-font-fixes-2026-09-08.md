# VAS 2.7.1: privacy and font regression verification

Date: September 8, 2026. Baseline: `76d1779868276255cd84bef8047a1f0a81c3a25e` (2.7.0).

## Scope and original failures

| Finding | Vulnerable path | Required invariant |
| --- | --- | --- |
| Handoff export | Existing-project UI synchronization restored raw task text before JSON serialization. | The complete downloaded document excludes recognized secrets, contacts, and private paths. |
| Credential filtering | Quoted JSON keys bypassed assignment filtering in browser/Python; source ZIP admission missed them. | Equivalent credential representations are removed from handoff data or cause source-file export refusal. |
| Memory deletion | Atomic replacement backed up the pre-deletion store; recovery/temp copies also retained removed events. | A successful explicit deletion leaves no removed event in VAS-managed history copies. |
| Windows fonts | Static MIME allowlist omitted `.ttf`. | Bundled fonts are delivered as binary font assets while the text API remains restricted. |

## Implementation boundaries

- `src/agent-contract.js` and `scripts/vas_ai_contract.py`: shared credential-aware cleaning, nested-field sanitization, and complete-document finalization before hashing.
- `src/agent-handoff-web.js`, `src/project-import.js`, and `src/client-export.js`: sanitized UI synchronization and awaited finalization at the download boundary.
- `scripts/vas_agent_handoff.py`: the same credential policy for Python handoffs and reviewed-source ZIP admission.
- `scripts/VAS.Memory.psm1`: explicit-deletion history purge under the existing mutex, with atomic replacement that creates no pre-deletion backup. Ordinary writes keep their backup behavior.
- `scripts/VAS.Server.psm1`: `.ttf` MIME entry only; text-access restrictions remain in place.
- `package.json` and Windows CI: include the new regression module in ongoing checks. Runtime, package, and UI version labels are synchronized to 2.7.1.

## Regression artifacts

- `tests/fixtures/secret-redaction-cases.json`: shared synthetic credential representations for browser/Python parity.
- `tests/privacy-regressions.spec.js`: real UI downloads after edits/provider changes; late mutation before save; independent SHA-256 calculation; legitimate design data controls.
- `tests/test_privacy_regressions.py`: Python generation/normalization, source ZIP refusal and valid excerpt preservation, real Windows deletion APIs, corrupt-store/missing-record deletion, and HTTP font delivery.

## Validation results

Outcome: **fixed** for the four scoped findings.

| Gate / command | Final result |
| --- | --- |
| `node --check src/agent-contract.js` and Python import/compile checks | Passed |
| `python -m pytest -q tests/test_privacy_regressions.py` | 29 passed, including actual Windows PowerShell 5.1 API execution |
| `npx playwright test -c tests/playwright.config.js tests/privacy-regressions.spec.js` | 2 passed |
| `npm.cmd run test:python` | 140 passed; 1 directory-symlink check skipped because this Windows account cannot create the test link |
| `npm.cmd run test:browser` | 77 passed |
| `npm.cmd run test:package` | 7 passed, including reproducibility, checksums and package boundaries |
| `python tests/test_release_runtime_flow.py` | 1 passed after extraction into a Korean path containing spaces |
| `python scripts/agent_checks.py security` | 4 package boundary checks, tracked-file boundary, and packaged-source hashes passed |
| Chrome rendering of the extracted Windows package | 1440px and 390px: Bricolage Grotesque loaded, no horizontal overflow, no page errors |

The original secret/contact/path markers no longer appear in actual UI downloads. All 20 shared credential/encoding cases are removed from browser/Python handoffs and refused by source ZIP export. Deleted markers are absent from the live store and all VAS-managed history copies after individual deletion, full clearing, replacement import, and corrupt-store recovery. The TTF response returns 200 with `font/ttf` and the expected binary hash; the text API still rejects it.

A fresh read-only reviewer found three candidate bypasses (prefixed credential keys, decoded sensitive strings, and assignments with comments). The parent reproduced each through actual source ZIP export, corrected the shared policy, and added regression cases. Template-quoted values and encoded private paths were also covered. There was one independent review cycle; no user records were used.

During development, the deletion test exposed PowerShell's null-string conversion in `File.Replace`; it now uses `[NullString]::Value`. A locked-history test confirms failed deletion returns an error and preserves the live store. One older browser assertion expected separate `[contact]`/`[secret]` markers; it now checks the shared `[redacted]` marker while retaining both original-value exclusion assertions. The full browser suite passed after that update.

The Windows font screens were visually compared with direct-file rendering of the same extracted assets. The mobile capture matched exactly; desktop differences were confined to the decorative image, outside the typography/layout under test. This is font and layout verification, not a claim of identical decorative-image rasterization.

## Preserved behavior and limits

Controls cover design color tokens, 700-line design guidance, complete agent instructions, public reference URLs, selected-folder availability in the copied prompt, correct final-payload hashes, safe source excerpts, surviving memory records, pause state, unrelated files, and denial of binary fonts through the text API.

All memory tests use isolated temporary state and fake records. No user's actual work-memory database or project data is inspected or changed by these checks. The original audit is retained as historical evidence; this record describes the patch separately.

Deletion covers application-managed previous, corrupt, and temporary files. It is not physical secure erasure and does not cover independent exports, OS backups, or NAS snapshots. Credential filtering recognizes supported field names and encodings, not every possible secret. This is a focused remediation of four findings, not a guarantee that the whole repository is free of vulnerabilities.

The optional 10-run stress suite is not run. Any environment-specific skipped checks are listed with the final results.
