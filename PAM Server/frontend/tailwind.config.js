/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          900: '#0a1628',
          800: '#0f1d3a',
          700: '#14284a',
          600: '#1a335c',
          500: '#1f3e6e',
        },
        slate: {
          850: '#172033',
          800: '#1e293b',
          700: '#334155',
          600: '#475569',
          500: '#64748b',
          400: '#94a3b8',
          300: '#cbd5e1',
          200: '#e2e8f0',
          100: '#f1f5f9',
        },
      },
      accent: {
        blue: '#3b82f6',
      },
    },
  },
  plugins: [],
};
