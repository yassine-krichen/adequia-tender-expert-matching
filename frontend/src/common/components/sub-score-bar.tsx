import type { LucideIcon } from 'lucide-react';

export function SubScoreBar({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: number | null;
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="flex w-32 items-center gap-1.5 text-muted-foreground">
        <Icon className="size-3.5 shrink-0" />
        {label}
      </span>
      {value == null ? (
        <span className="flex-1 text-muted-foreground italic">
          Checked as pass/fail only, not scored
        </span>
      ) : (
        <>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted" role="presentation">
            <div className="h-full bg-primary" style={{ width: `${Math.round(value * 100)}%` }} />
          </div>
          <span className="w-8 text-right text-muted-foreground">{Math.round(value * 100)}%</span>
        </>
      )}
    </div>
  );
}
