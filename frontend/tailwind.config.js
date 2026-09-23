/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Montserrat', 'sans-serif'],
        display: ['Limelight', 'cursive'],
      },
      colors: {
        cream: '#f4efe4',
        'cream-dark': '#eee6d3',
        gold: '#c8a24a',
        'gold-dark': '#a5822f',
        ink: '#141414',
      },
    },
  },
  plugins: [],
}
