# New design collection — source and asset notes

Researched 2026-09-07. The ten VAS profiles and compositions are original adaptations. No external skill was installed globally, and external instructions do not override user choices or host permissions.

| Primary source | Reviewed revision | Applied idea |
| --- | --- | --- |
| [Anthropic frontend-design](https://github.com/anthropics/skills/blob/41bbe19d1a1a7eaab5e7bb9050a417e5c6cffc8f/skills/frontend-design/SKILL.md) | 41bbe19 | A deliberate identity expressed through type, composition and real media |
| [Taste Skill](https://github.com/Leonxlnx/taste-skill/tree/ccbc15639c97057cbfcf32ecebc38ef716e4bb37) | ccbc156 | Vary layout, density and motion; avoid uniform generic sections |
| [UI UX Pro Max style catalogue](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/4aad0584d92131626b16d4ff4d77f0455385013c/src/ui-ux-pro-max/data/styles.csv) | 4aad058 | Distinct glass, clay, bento, organic, retro, Swiss and kinetic style families |

The public catalog contains the ten new collections plus four curated sample sites: Awwwards (FORM / FIELD architecture), Linear (ORBIT project board), Stripe (RELAY subscriptions) and Notion (FIELDNOTES wiki). Each has an independent composition and maintained agent profile. Other previous preset data remains for saved-setting compatibility and is not listed as a new choice.

## Assets

- VAS 2.15.0 removed the bundled sample artwork, the six local fonts and the Morrow proof app to keep the starter small. The ten compositions and four sample sites remain as native HTML/CSS; where an image used to sit, a colour block drawn from the palette stands in.
- The font names in `ui/design-collection.css` describe each composition’s direction. No font binary ships, so previews fall back to the generic family at the end of each stack.
- Target projects provision their own licensed fonts and imagery. The agent asks once for a reference design or site and otherwise plans the design itself.
- The removed artwork was original generated imagery and rendered-site screenshots captured for the samples; it remains in the 2.14.0 release and earlier.

## design-craft skill

`.agents/skills/design-craft/` is original VAS text written for this project. It is not a copy or translation of an external skill.

| Informed by | Applied idea |
| --- | --- |
| Anthropic frontend-design skill (read from a locally installed copy; upstream revision not pinned) | Plan palette, type and layout from the subject before coding; question generic defaults; spend boldness in one place |
| W3C WCAG 2.2 SC 1.4.3, 1.4.10, 2.5.5 | Text contrast, 320 CSS px reflow and target size used as review baselines |
| VAS project verification records | Checks passing while composition stayed weak; Korean sentence endings stranded on narrow screens; decisions asked again in later conversations |

The skill adds no approval step, external service, font download or global installation. User requests, saved project instructions and confirmed tokens take priority over it.
