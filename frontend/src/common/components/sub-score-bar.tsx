export function SubScoreBar({ label, value }: { label: string; value: number }) {
  const percent = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-32 text-muted-foreground">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted" role="presentation">
        <div className="h-full bg-primary" style={{ width: `${percent}%` }} />
      </div>
      <span className="w-8 text-right text-muted-foreground">{percent}%</span>
    </div>
  );
}
