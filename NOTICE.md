# NOTICE

This notice summarizes public-release attribution candidates for VAS 2.5.2.

## Project

- VAS 2.5.2 (Vibecoding Agent System)
- Original author: QUINTPACT Team
- Korean author name: 퀀트펙트 팀
- License: MIT License
- Copyright holder: QUINTPACT Team

## Third-Party References

- Pretendard is loaded from jsDelivr and the upstream `orioncactus/pretendard` project. Upstream license: SIL Open Font License 1.1.
- Google Fonts CSS is referenced for Geist Mono, Inter, and JetBrains Mono. Google Fonts families are distributed under open font licenses; verify each upstream family page before vendoring font files.
- Playwright / `@playwright/test` is referenced by `tests/package.json` and `tests/package-lock.json` for local browser smoke tests. Upstream license: Apache License 2.0.

## Bundling Notes

- `node_modules/` is intentionally excluded from this release candidate.
- External font files are not vendored in this folder; the HTML/CSS files reference CDN-hosted CSS.
- Claude, Figma, GitHub, Google Fonts, jsDelivr, Microsoft, and Playwright names appear as tool, integration, or dependency references and remain the property of their respective owners.

## Release Note

TASK-039 applied the MIT License in the root `LICENSE` file. Public GitHub upload, NAS upload, external distribution, and archive creation still require separate project-owner approval in this handoff workflow.
