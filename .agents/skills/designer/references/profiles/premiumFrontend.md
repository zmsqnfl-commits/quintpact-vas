# Premium Frontend

- Composition: for a workspace use a compact navigation bar or 216-240px sidebar, a page heading with one primary action, a short summary strip, then the main project list. Marketing pages require their own story and visual hierarchy.
- Hierarchy: use body text as the base, page title at 2-2.25 times base, section titles at 1.2 times, and metadata at 0.8-0.875 times. Keep Korean UI text on the sans stack; reserve monospace for identifiers and numbers.
- Density: use the confirmed padding token for panels and half that spacing between related controls. Aim for 44px primary controls and 56-72px project rows with aligned name, owner, status and next action.
- Surfaces: background establishes the workspace; a single surface layer groups content. Prefer dividers within lists, borders for interactive controls, and shadows only for floating layers.
- Identity: select one content-led visual motif such as progress tracks, issue identifiers or compact thumbnails. Give the primary action enough contrast and use secondary buttons with lower visual weight.
- States: implement selected navigation, hover, visible keyboard focus, loading, empty and error states with useful next actions. Never invent healthy operational statistics for production screens.
- Responsive: move sidebar navigation to an accessible drawer on small screens; put actions below titles and project metadata below the main label. Preserve meaningful row order at 320px.
- Preserve confirmed tokens and reference assets. Compare the actual browser result at 390px and desktop for type hierarchy, density, alignment, color contrast and working controls.
