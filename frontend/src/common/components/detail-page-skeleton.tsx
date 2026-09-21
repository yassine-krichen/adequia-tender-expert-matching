import { Card, CardContent, CardHeader } from '@/common/components/ui/card';
import { Skeleton } from '@/common/components/ui/skeleton';

// Shared loading shape for the candidate/TDR/match detail pages: title bar +
// a couple of text lines + a table-row block, so the loading state roughly
// matches the loaded card layout instead of a bare "Loading…" text jump.
export function DetailPageSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-1/3" />
      </CardHeader>
      <CardContent className="space-y-4">
        <Skeleton className="h-4 w-1/4" />
        <Skeleton className="h-4 w-1/5" />
        <div className="space-y-2 pt-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      </CardContent>
    </Card>
  );
}
