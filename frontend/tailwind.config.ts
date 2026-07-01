import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      borderRadius: {
        DEFAULT: '0px',
        none: '0px',
        full: '9999px',
      },
      fontFamily: {
        heading: ['var(--font-space-grotesk)'],
        body: ['var(--font-inter)'],
      },
      colors: {
        background: '#0B0F14',
        foreground: '#E6E8EB',
        primary: '#6C5CE7',
        secondary: '#0F766E',
        success: '#22C55E',
        warning: '#F59E0B',
        danger: '#EF4444',
        muted: '#64748B',
      },
    },
  },
  plugins: [],
};

export default config;
