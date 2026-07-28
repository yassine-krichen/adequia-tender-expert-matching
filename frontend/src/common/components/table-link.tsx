import { ChevronRight } from 'lucide-react';
import Link from 'next/link';

/**
 * Styled row-link for tables: without an explicit className, Tailwind's
 * preflight resets anchors to plain text color, making them visually
 * indistinguishable from surrounding table cells. Used identically across
 * the candidates, TDRs, and TDR-positions-matches tables.
 */
export function TableLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="inline-flex items-center gap-1 font-medium text-primary hover:underline">
      {children}
      <ChevronRight className="size-3.5 shrink-0" />
    </Link>
  );
}
