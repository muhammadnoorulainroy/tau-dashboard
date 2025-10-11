/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#fef5e7',
          100: '#fdebd0',
          200: '#fad7a0',
          300: '#f8c471',
          400: '#f5b041',
          500: '#f39c12',
          600: '#d68910',
          700: '#b9770e',
          800: '#9c640c',
          900: '#7e5109',
        },
        success: {
          50: '#eafaf1',
          100: '#d5f4e6',
          200: '#abebc6',
          300: '#82e1a6',
          400: '#58d886',
          500: '#2ecc71',
          600: '#27ae60',
          700: '#229954',
          800: '#1e8449',
          900: '#196f3d',
        },
        warning: {
          50: '#fef9e7',
          100: '#fcf3cf',
          200: '#f9e79f',
          300: '#f7dc6f',
          400: '#f4d03f',
          500: '#f1c40f',
          600: '#d4ac0d',
          700: '#b7950b',
          800: '#9a7d0a',
          900: '#7d6608',
        },
        danger: {
          50: '#fdedec',
          100: '#fadbd8',
          200: '#f5b7b1',
          300: '#f1948a',
          400: '#ec7063',
          500: '#e74c3c',
          600: '#cb4335',
          700: '#af3a2e',
          800: '#943126',
          900: '#78281f',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [],
}


