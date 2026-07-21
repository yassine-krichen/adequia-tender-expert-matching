'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import { cn } from '@/common/lib/utils';
import { requestGuidedTour } from '@/features/tour/use-guided-tour';

const LINKS = [
  { href: '/', label: 'Home' },
  { href: '/candidates', label: 'Candidates' },
  { href: '/tdrs', label: 'TDRs' },
  { href: '/metrics', label: 'Metrics' },
];

export function TopNav() {
  const pathname = usePathname();
  const router = useRouter();

  function handleTakeTour() {
    requestGuidedTour(() => router.push('/tdrs'), pathname === '/tdrs');
  }

  return (
    <nav className="border-b border-border">
      <div className="mx-auto flex max-w-2xl items-center justify-between gap-1 px-8 py-3">
        <div className="flex items-center gap-1">
          {LINKS.map((link) => {
            const isActive = link.href === '/' ? pathname === '/' : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  'rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </div>
        <button
          type="button"
          onClick={handleTakeTour}
          className="rounded-md px-2.5 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          Take the tour
        </button>
      </div>
    </nav>
  );
}
