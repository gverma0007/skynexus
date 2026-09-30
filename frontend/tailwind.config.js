/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'sky-bg': 'var(--color-bg-dark)',
        'sky-panel': 'var(--color-bg-panel)',
        'sky-text': 'var(--color-text-primary)',
        'sky-muted': 'var(--color-text-secondary)',
        'sky-accent': 'var(--color-accent-blue)',
        'sky-red': 'var(--color-accent-red)',
        'sky-green': 'var(--color-accent-green)',
        'sky-amber': 'var(--color-accent-amber)',
      },
    },
  },
  plugins: [],
}
