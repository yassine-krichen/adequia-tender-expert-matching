import type { Metadata } from 'next';
import { Inter, Space_Grotesk } from 'next/font/google';

import '@/styles/globals.css';

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-space-grotesk',
});

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
});

export const metadata: Metadata = {
  title: 'AdéquIA',
  description: 'Le bon profil, pour la bonne mission.',
};

export function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className="dark">
      <body className={`${spaceGrotesk.variable} ${inter.variable} font-body`}>{children}</body>
    </html>
  );
}

export default RootLayout;
