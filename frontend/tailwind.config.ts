// frontend/tailwind.config.ts

import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#fffbeb',  // amber-50
          100: '#fef3c7', // amber-100
          500: '#f59e0b', // amber-500
          600: '#d97706', // amber-600
          700: '#b45309', // amber-700
        }
      },
    },
  },
  plugins: [
    typography,
  ],
};
export default config;