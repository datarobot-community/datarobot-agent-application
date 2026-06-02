/**
 * Replacement for shiki's themes.mjs — only includes the 2 themes used by the app.
 */
const bundledThemesInfo = [
  {
    id: 'github-light',
    displayName: 'GitHub Light',
    type: 'light' as const,
    import: () => import('@shikijs/themes/github-light'),
  },
  {
    id: 'github-dark-dimmed',
    displayName: 'GitHub Dark Dimmed',
    type: 'dark' as const,
    import: () => import('@shikijs/themes/github-dark-dimmed'),
  },
];

const bundledThemes = Object.fromEntries(bundledThemesInfo.map(i => [i.id, i.import]));

export { bundledThemes, bundledThemesInfo };
