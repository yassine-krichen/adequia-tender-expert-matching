import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';

import { Button } from '@/common/components/ui/button';

export function BackLink({ href, label = 'Back' }: { href: string; label?: string }) {
  return (
    <Button asChild variant="ghost" size="sm" className="-ml-2.5">
      <Link href={href}>
        <ArrowLeft />
        {label}
      </Link>
    </Button>
  );
}
