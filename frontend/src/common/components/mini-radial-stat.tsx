'use client';

import { Label, PolarGrid, PolarRadiusAxis, RadialBar, RadialBarChart } from 'recharts';

import { ChartContainer, type ChartConfig } from '@/common/components/ui/chart';
import { cn } from '@/common/lib/utils';

const SIZE_CLASSES = {
  sm: 'max-h-[90px]',
  md: 'max-h-[140px]',
} as const;

const CENTER_TEXT_CLASSES = {
  sm: 'text-lg',
  md: 'text-2xl',
} as const;

/**
 * Small single-value radial gauge (shadcn "radial text" variant). Used by
 * the About page's metrics teaser, and reused by the metrics page for the
 * guardrails/scoring_agreement single-KPI groups.
 */
export function MiniRadialStat({
  label,
  value,
  centerLabel,
  size = 'md',
  muted = false,
  className,
}: {
  label: string;
  /** 0..1 fraction. Values outside that range are clamped for the gauge fill. */
  value: number;
  centerLabel?: string;
  size?: keyof typeof SIZE_CLASSES;
  muted?: boolean;
  className?: string;
}) {
  const percent = Math.max(0, Math.min(100, Math.round(value * 100)));
  const data = [{ name: label, stat: percent, fill: 'var(--color-stat)' }];
  const config: ChartConfig = {
    stat: { label, color: muted ? 'var(--chart-4)' : 'var(--chart-1)' },
  };

  return (
    <div className={cn('flex flex-col items-center', muted && 'opacity-70', className)}>
      <ChartContainer
        config={config}
        className={cn('mx-auto aspect-square w-full', SIZE_CLASSES[size])}
      >
        <RadialBarChart
          data={data}
          startAngle={90}
          endAngle={90 - (360 * percent) / 100}
          innerRadius="72%"
          outerRadius="100%"
        >
          <PolarGrid
            gridType="circle"
            radialLines={false}
            stroke="none"
            className="first:fill-muted last:fill-background"
          />
          <RadialBar dataKey="stat" background cornerRadius={999} />
          <PolarRadiusAxis tick={false} tickLine={false} axisLine={false}>
            <Label
              content={({ viewBox }) => {
                if (viewBox && 'cx' in viewBox && 'cy' in viewBox) {
                  return (
                    <text
                      x={viewBox.cx}
                      y={viewBox.cy}
                      textAnchor="middle"
                      dominantBaseline="middle"
                    >
                      <tspan
                        x={viewBox.cx}
                        y={viewBox.cy}
                        className={cn('fill-foreground font-semibold', CENTER_TEXT_CLASSES[size])}
                      >
                        {centerLabel ?? `${percent}%`}
                      </tspan>
                    </text>
                  );
                }
                return null;
              }}
            />
          </PolarRadiusAxis>
        </RadialBarChart>
      </ChartContainer>
      <p className="text-center text-xs text-muted-foreground">{label}</p>
    </div>
  );
}
