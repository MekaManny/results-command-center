/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        command: {
          red: "#c1121f",
          black: "#111111",
          line: "#e5e7eb",
        },
      },
      boxShadow: {
        panel: "0 1px 2px rgba(17, 17, 17, 0.06)",
      },
    },
  },
  plugins: [],
};
