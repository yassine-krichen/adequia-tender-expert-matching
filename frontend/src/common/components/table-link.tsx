import { ChevronRight } from 'lucide-react';
import Link from 'next/link';

import { cn } from '@/common/lib/utils';

/**
 * Styled row-link for tables: without an explicit className, Tailwind's
 * preflight resets anchors to plain text color, making them visually
 * indistinguishable from surrounding table cells. Used identically across
 * the candidates, TDRs, and TDR-positions-matches tables.
 */
export function TableLink({
  href,
  children,
  className,
  ...props
}: React.ComponentProps<typeof Link>) {
  return (
    <Link
      href={href}
      className={cn(
        'inline-flex items-center gap-1 font-medium text-primary hover:underline',
        className
      )}
      {...props}
    >
      <span className="truncate">{children}</span>
      <ChevronRight className="size-3.5 shrink-0" />
    </Link>
  );
}
