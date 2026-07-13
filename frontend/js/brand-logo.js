/** Inline HerbaGraph logo mark (network graph + blue terminal node). */
window.HERBAGRAPH_LOGO_MARK_SVG = `<svg class="logo-mark" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <path d="M5 22 L13 14 L20 18 L27 8" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="5" cy="22" r="2.25" fill="currentColor"/>
  <circle cx="13" cy="14" r="2.25" fill="currentColor"/>
  <circle cx="20" cy="18" r="2.25" fill="currentColor"/>
  <circle cx="27" cy="8" r="2.75" fill="#2f7df6"/>
</svg>`;

function herbagraphLogoLink(href, opts) {
  opts = opts || {};
  const showWord = opts.wordmark !== false;
  const tag = opts.tagline ? `<span class="logo-tag">${opts.tagline}</span>` : "";
  const word = showWord ? `<span class="logo-word">HerbaGraph</span>` : "";
  const stack = tag
    ? `<span class="logo-stack">${word}${tag}</span>`
    : word;
  return `<a class="logo" href="${href}">${window.HERBAGRAPH_LOGO_MARK_SVG}${stack}</a>`;
}