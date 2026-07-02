import type { Config } from 'tailwindcss';

const rgbVar = (name: string) => `rgb(var(${name}) / <alpha-value>)`;

const config: Config = {
  darkMode: 'class',
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      borderRadius: {
        lg: 'var(--radius-lg)',
        md: 'var(--radius-md)',
        sm: 'var(--radius-sm)',
        xl: 'var(--radius-xl)',
        full: '9999px',
      },
      fontFamily: {
        heading: ['var(--font-heading)'],
        body: ['var(--font-sans)'],
        sans: ['var(--font-sans)'],
      },
      colors: {
        background: rgbVar('--background'),
        foreground: rgbVar('--foreground'),
        card: {
          DEFAULT: rgbVar('--card'),
          foreground: rgbVar('--card-foreground'),
        },
        popover: {
          DEFAULT: rgbVar('--popover'),
          foreground: rgbVar('--popover-foreground'),
        },
        primary: {
          DEFAULT: rgbVar('--primary'),
          foreground: rgbVar('--primary-foreground'),
        },
        secondary: {
          DEFAULT: rgbVar('--secondary'),
          foreground: rgbVar('--secondary-foreground'),
        },
        muted: {
          DEFAULT: rgbVar('--muted'),
          foreground: rgbVar('--muted-foreground'),
        },
        accent: {
          DEFAULT: rgbVar('--accent'),
          foreground: rgbVar('--accent-foreground'),
        },
        destructive: {
          DEFAULT: rgbVar('--destructive'),
          foreground: rgbVar('--destructive-foreground'),
        },
        success: {
          DEFAULT: rgbVar('--success'),
          foreground: rgbVar('--success-foreground'),
        },
        warning: {
          DEFAULT: rgbVar('--warning'),
          foreground: rgbVar('--warning-foreground'),
        },
        // border/input are subtle hairlines — a fixed low opacity on the
        // foreground color, not an adjustable utility like the others.
        border: 'rgb(var(--border) / 0.12)',
        input: 'rgb(var(--input) / 0.15)',
        ring: rgbVar('--ring'),
      },
    },
  },
  plugins: [],
};

export default config;
