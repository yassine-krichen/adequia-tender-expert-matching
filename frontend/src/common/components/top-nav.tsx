'use client';

import { BarChart3, Compass, FileText, Home, Info, Monitor, Moon, Sun, Users } from 'lucide-react';
import { useTheme } from 'next-themes';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import { Button } from '@/common/components/ui/button';
import { cn } from '@/common/lib/utils';
import { requestGuidedTour } from '@/features/tour/use-guided-tour';

const LINKS = [
  { href: '/', label: 'Home', icon: Home },
  { href: '/candidates', label: 'Candidates', icon: Users },
  { href: '/tdrs', label: 'TDRs', icon: FileText },
  { href: '/metrics', label: 'Metrics', icon: BarChart3 },
  { href: '/about', label: 'About', icon: Info },
];

const THEME_CYCLE = { light: 'dark', dark: 'system', system: 'light' } as const;

const THEME_ICON = { light: Sun, dark: Moon, system: Monitor } as const;

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const current = (theme ?? 'system') as keyof typeof THEME_CYCLE;
  const Icon = THEME_ICON[current] ?? Monitor;

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      aria-label="Toggle theme"
      onClick={() => setTheme(THEME_CYCLE[current] ?? 'light')}
    >
      <Icon className="size-4" />
    </Button>
  );
}

export function TopNav() {
  const pathname = usePathname();
  const router = useRouter();

  function handleTakeTour() {
    requestGuidedTour(() => router.push('/tdrs'), pathname === '/tdrs');
  }

  return (
    <nav className="border-b border-border">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-1 px-8 py-3">
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
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handleTakeTour}
            className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <Compass className="size-4" />
            Take the tour
          </button>
          <ThemeToggle />
        </div>
      </div>
    </nav>
  );
}
