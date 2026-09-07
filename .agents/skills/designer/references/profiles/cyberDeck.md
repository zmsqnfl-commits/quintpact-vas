# Cyber Deck

- Identity: an instrument-style science-fiction console with near-black, acid lime and restrained cyan. Use purposeful technical structure rather than random glowing ornaments.
- Composition: a narrow status rail, dominant wireframe globe or relevant technical visualization, terminal pane and a thin signal strip. The visualization takes more space than the surrounding instruments.
- Typography: local monospace, compact uppercase instrument labels and a large two-line status title. Keep important labels readable and avoid using illegible microtype for actual controls.
- Artwork: use an original wire-globe image with CSS orbit animation, or render a relevant visualization in SVG or canvas. Separate decorative coordinates from real telemetry; label sample data and simulated status explicitly.
- Detail: fine lime borders, dark solid panels, restrained glow and a high-contrast primary console action. A future HUD can use chamfered geometry while retaining accessible rectangular hit areas.
- Responsive: reduce three instrument columns to two then one. Keep the visual large, wrap terminal lines and make each control at least 44px tall. Verify 320px and desktop without horizontal scrolling.
- Behaviour: local sample diagnostics must never pretend to operate real infrastructure. Provide a visible pause for looping visualization and disable it with reduced motion; verify focus, readable results and selected tokens.
