/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink:      '#17171c',
        canvas:   '#ffffff',
        stone:    '#eeece7',
        hairline: '#d9d9dd',
        muted:    '#93939f',
        slate:    '#75758a',
        'body-muted': '#616161',
        'deep-green': '#003c33',
        'pale-green': '#edfce9',
        'action-blue': '#1863dc',
        coral:    '#ff7759',
        'error-red': '#b30000',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui'],
        mono: ['ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      borderRadius: {
        xs:   '4px',
        sm:   '8px',
        md:   '16px',
        lg:   '22px',
        pill: '32px',
      },
    },
  },
  plugins: [],
}
