/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Calm blue — primary actions
        primary: {
          50: '#EEF5FB',
          100: '#D7E9F6',
          400: '#7FB4E0',
          500: '#5B9BD5',
          600: '#3F7FBD',
          700: '#2E638F',
          900: '#1B3A54',
        },
        // Soft green — secondary accents, success, priority highlights
        secondary: {
          50: '#F1FAF4',
          100: '#DCF0E2',
          400: '#BCE0C8',
          500: '#A8D5BA',
          600: '#7EB690',
        },
        // Muted orange — warnings, alerts (replaces harsh red)
        warn: {
          100: '#FCE9D6',
          400: '#E3A56B',
          500: '#D98C4A',
          600: '#B96F31',
        },
        offwhite: '#F7FAFC',
        charcoal: '#263238',
        // kept for backwards compatibility with a few older class names
        cream: '#F7FAFC',
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
        card: '0 1px 2px rgba(38,50,56,0.04), 0 4px 12px -4px rgba(38,50,56,0.08)',
        soft: '0 1px 3px rgba(38,50,56,0.08)',
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
