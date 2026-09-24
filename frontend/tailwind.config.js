/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Calm blue — primary actions
        primary: {
          50: '#F3F8FC',
          100: '#E2EEF7',
          400: '#8DB9D8',
          500: '#6A9FC4',
          600: '#527FA0',
          700: '#3F667F',
          900: '#29495E',
        },
        // Soft green — secondary accents, success, priority highlights
        secondary: {
          50: '#F4F8F5',
          100: '#E4EFE8',
          400: '#B8D3C2',
          500: '#A8C9B3',
          600: '#7FA48B',
        },
        // Muted orange — warnings, alerts (replaces harsh red)
        warn: {
          100: '#FCE9D6',
          400: '#E3A56B',
          500: '#D98C4A',
          600: '#B96F31',
        },
        offwhite: '#F8FAFB',
        charcoal: '#263842',
        // kept for backwards compatibility with a few older class names
        cream: '#F8FAFB',
        leaf: '#7EB690',
        coral: '#D98C4A',
      },
      fontFamily: {
        display: ['Poppins', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
      },
      fontSize: {
        base: ['1.125rem', '1.7'],
        lg: ['1.3rem', '1.7'],
        xl: ['1.6rem', '1.5'],
      },
      boxShadow: {
        card: '0 18px 45px -28px rgba(35,73,94,0.28), 0 2px 8px rgba(35,73,94,0.05)',
        soft: '0 8px 24px -18px rgba(35,73,94,0.35)',
      },
      keyframes: {
        ripple: {
          '0%': { transform: 'scale(1)', opacity: '0.45' },
          '100%': { transform: 'scale(2.2)', opacity: '0' },
        },
        pulseSoft: {
          '0%, 100%': { transform: 'scale(1)' },
          '50%': { transform: 'scale(1.03)' },
        },
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        ripple1: 'ripple 1.8s ease-out infinite',
        ripple2: 'ripple 1.8s ease-out 0.6s infinite',
        ripple3: 'ripple 1.8s ease-out 1.2s infinite',
        pulseSoft: 'pulseSoft 2.2s ease-in-out infinite',
        fadeUp: 'fadeUp 0.35s ease-out both',
      },
    },
  },
  plugins: [],
}
