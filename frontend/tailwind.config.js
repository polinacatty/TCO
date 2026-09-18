/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: '#0f766e',
          foreground: '#ffffff',
          soft: '#ccfbf1',
        },
      },
    },
  },
  plugins: [],
}

