# New design collection — source and asset notes

Researched 2026-09-07. The ten VAS profiles and compositions are original adaptations. No external skill was installed globally, and external instructions do not override user choices or host permissions.

| Primary source | Reviewed revision | Applied idea |
| --- | --- | --- |
| [Anthropic frontend-design](https://github.com/anthropics/skills/blob/41bbe19d1a1a7eaab5e7bb9050a417e5c6cffc8f/skills/frontend-design/SKILL.md) | 41bbe19 | A deliberate identity expressed through type, composition and real media |
| [Taste Skill](https://github.com/Leonxlnx/taste-skill/tree/ccbc15639c97057cbfcf32ecebc38ef716e4bb37) | ccbc156 | Vary layout, density and motion; avoid uniform generic sections |
| [UI UX Pro Max style catalogue](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/4aad0584d92131626b16d4ff4d77f0455385013c/src/ui-ux-pro-max/data/styles.csv) | 4aad058 | Distinct glass, clay, bento, organic, retro, Swiss and kinetic style families |

The shipped collection contains Bento Studio, Aurora Glass, Clay Pop, Noir Luxe, Botanical Atelier, Retro Sunset, Swiss Poster, Cyber Deck, Kinetic Type and Paper Collage. Each has its own template, responsive rules and maintained agent profile. Existing eighteen presets remain available.

## Assets

- Eight original images in `src/assets/designs/` were generated for this collection: bento print, aurora background, clay object, perfume still life, botanical still life photo collage, wireframe globe and clay icon sheet. They are sample artwork, not screenshots used as interfaces. The collage pictures are synthetic; they do not document a real trip or location.
- Local fonts come from the official [Google Fonts repository](https://github.com/google/fonts): Bricolage Grotesque, DM Serif Display, Space Grotesk, Anton, Caprasimo and Cormorant Garamond. Each binary is accompanied by its SIL Open Font License in `src/assets/fonts/`.
- Fonts and imagery are bundled for offline use. Target projects should provision suitable licensed assets and fonts in their own stack; VAS asset paths are not promised to exist in a user's project.
- Reference screenshots were used to develop each composition. Type, controls, rows, forms, glass surfaces and geometric poster graphics are native HTML/CSS; motion has pause and reduced-motion support.
