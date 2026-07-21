import type { LucideIcon } from 'lucide-react';

import { Card, CardContent } from '@/common/components/ui/card';
import { cn } from '@/common/lib/utils';

interface EmptyStateProps extends React.ComponentProps<typeof Card> {
  icon: LucideIcon;
  title: string;
  description: string;
}

// Card-based "explain, don't just show blank" placeholder — mirrors
// FileUpload's dashed-border empty-dropzone visual style so empty states
// and upload affordances read as the same visual language.
export function EmptyState({
  icon: Icon,
  title,
  description,
  className,
  ...props
}: EmptyStateProps) {
  return (
    <Card className={cn('border-dashed shadow-none ring-0', className)} {...props}>
      <CardContent className="flex flex-col items-center gap-3 py-8 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
          <Icon className="h-5 w-5 text-muted-foreground" />
        </div>
        <div className="space-y-1">
          <p className="text-sm font-medium">{title}</p>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
      </CardContent>
    </Card>
  );
}
