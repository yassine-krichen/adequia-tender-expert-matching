'use client';

import { BarChart3, Compass, FileText, Home, Users } from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import { cn } from '@/common/lib/utils';
import { requestGuidedTour } from '@/features/tour/use-guided-tour';

const LINKS = [
  { href: '/', label: 'Home', icon: Home },
  { href: '/candidates', label: 'Candidates', icon: Users },
  { href: '/tdrs', label: 'TDRs', icon: FileText },
  { href: '/metrics', label: 'Metrics', icon: BarChart3 },
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
            const Icon = link.icon;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
              >
                <Icon className="size-4" />
                {link.label}
              </Link>
            );
          })}
        </div>
        <button
          type="button"
          onClick={handleTakeTour}
          className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <Compass className="size-4" />
          Take the tour
        </button>
      </div>
    </nav>
  );
}
