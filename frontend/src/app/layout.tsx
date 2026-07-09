import type { Metadata } from 'next';
import { Geist_Mono, Inter, Space_Grotesk } from 'next/font/google';

import { ThemeProvider } from '@/common/components/theme-provider';
import { TopNav } from '@/common/components/top-nav';
import { cn } from '@/common/lib/utils';
import '@/styles/globals.css';

const spaceGroteskHeading = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-heading',
});

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });

const fontMono = Geist_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
});

export const metadata: Metadata = {
  title: 'AdéquIA',
  description: 'Le bon profil, pour la bonne mission.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="fr"
      suppressHydrationWarning
      className={cn('antialiased', fontMono.variable, 'font-sans', inter.variable, spaceGroteskHeading.variable)}
    >
      <body>
        <ThemeProvider>
          <TopNav />
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
