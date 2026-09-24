/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        teal: {
          950: '#0A3838',
          900: '#0F4C4C',
          800: '#166363',
          100: '#DCEEEE',
          50: '#F0F8F8',
        },
        gold: {
          600: '#C9861F',
          500: '#E8A33D',
          400: '#EEB65E',
          100: '#FBEBD2',
        },
        cream: '#FBF8F2',
        charcoal: '#2B2B2B',
        coral: '#E8674A',
        leaf: '#4A7C59',
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
      keyframes: {
        ripple: {
          '0%': { transform: 'scale(1)', opacity: '0.55' },
          '100%': { transform: 'scale(2.4)', opacity: '0' },
        },
        pulseSoft: {
          '0%, 100%': { transform: 'scale(1)' },
          '50%': { transform: 'scale(1.04)' },
        },
      },
      animation: {
        ripple1: 'ripple 1.8s ease-out infinite',
        ripple2: 'ripple 1.8s ease-out 0.6s infinite',
        ripple3: 'ripple 1.8s ease-out 1.2s infinite',
        pulseSoft: 'pulseSoft 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
