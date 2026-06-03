// Apply Global Theme Tokens

// Stark Neo-Brutalism signature default values to restore original system identity
const neobrutalDefault = {
  fontFamily: "'Pretendard', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif",
  fontSize: 16,
  fsHero: "56px",
  fsH2: "35.2px",
  fsH3: "24px",
  fsBody: "16px",
  fsSm: "12.8px",
  letterSpacing: -0.05,
  padding: 24,
  radius: 0,
  borderWidth: 2,
  shadow: 0,
  speed: 0.1,
  colors: {
    primary: '#000000',
    background: '#f5f5f4', // Align with main stylesheet bg
    surface: '#ffffff',    // Card default surface
    text: '#09090b',
    border: '#09090b',
    success: '#10b981'
  }
};

const CURRENT_VERSION = '2.5.2';
const savedVersion = localStorage.getItem('vasThemeTokensVersion');

if (savedVersion !== CURRENT_VERSION) {
    localStorage.setItem('vasThemeTokens', JSON.stringify(neobrutalDefault));
    localStorage.setItem('vasThemeTokensVersion', CURRENT_VERSION);
}

const savedTokens = localStorage.getItem('vasThemeTokens');

if (savedTokens) {

    try {

        const v = JSON.parse(savedTokens);
        
        // Auto-patch font family to guarantee Pretendard is the main body font with robust system fallback
        const systemFallback = ", system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif";
        const monoFallback = ", ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace";

        if (v.fontFamily && v.fontFamily.includes('Geist Mono')) {
           v.fontFamily = "'Pretendard'" + systemFallback;
        } else if (v.fontFamily && !v.fontFamily.includes('Pretendard')) {
           v.fontFamily = v.fontFamily.replace(", sans-serif", ", 'Pretendard'" + systemFallback).replace(", monospace", ", 'Pretendard'" + monoFallback);
        }
        
        document.documentElement.style.setProperty('--bg-color', v.colors.background);

        document.documentElement.style.setProperty('--text-main', v.colors.text);

        document.documentElement.style.setProperty('--text-muted', v.colors.text);

        document.documentElement.style.setProperty('--accent', v.colors.primary);

        document.documentElement.style.setProperty('--card-bg', v.colors.surface);

        document.documentElement.style.setProperty('--border', v.colors.border);

        document.documentElement.style.setProperty('--border-dark', v.colors.text);



        const style = document.createElement('style');

        let css = `

            body { font-family: ${v.fontFamily}; }

            .block .bl-content, .v-block .vl-content {

                border-radius: ${v.radius}px;

                padding: ${v.padding}px;

                border: ${v.borderWidth}px solid var(--border);

            }

        `;

        if (v.colors.border === '#000000' && v.borderWidth >= 3 && v.shadow === 0 && v.radius === 0) {

            css += `

                .block input:checked + .bl-content { background: var(--text-main); color: var(--bg-color); border-color: var(--text-main); transform: translate(-4px, -4px); box-shadow: 6px 6px 0px var(--accent); }

                .v-block input:checked + .vl-content { background: var(--text-main); color: var(--bg-color); border-color: var(--text-main); transform: translate(-4px, -4px); box-shadow: 6px 6px 0px var(--accent); }

            `;

        } else {

            let shadowStr = v.shadow > 0 ? `0 ${v.shadow/2}px ${v.shadow}px rgba(0,0,0,0.15)` : `4px 4px 0px var(--border-dark)`;

            let transformStr = v.shadow > 0 ? `translateY(-4px) scale(0.98)` : `translate(-4px, -4px)`;

            css += `

                .block input:checked + .bl-content { background: var(--text-main); color: var(--bg-color); border-color: var(--text-main); box-shadow: ${shadowStr}; transform: ${transformStr}; }

                .v-block input:checked + .vl-content { background: var(--text-main); color: var(--bg-color); border-color: var(--text-main); box-shadow: ${shadowStr}; transform: ${transformStr}; }

            `;

        }

        css += `

            .hero-section { background: var(--text-main); color: var(--bg-color); }

            .hero-meta { color: var(--bg-color); opacity: 0.7; }

            .back-link { color: var(--bg-color); }

            .hero-title p { color: var(--bg-color); opacity: 0.8; }

            .progress-indicator { color: var(--bg-color); }

            .progress-indicator span { color: var(--bg-color); opacity: 0.6; }

            .drag-drop-zone { background: var(--bg-color); border-color: var(--border); }

        `;

        style.textContent = css;

        document.head.appendChild(style);
        
        // 현재 적용된 프리셋명 표시 (#7)
        const currentPreset = localStorage.getItem('vasCurrentPreset');
        const themeSpan = document.getElementById('themeNameSpan');
        if (themeSpan && currentPreset) {
            themeSpan.textContent = currentPreset.charAt(0).toUpperCase() + currentPreset.slice(1);
        }

    } catch(e) {}

}
