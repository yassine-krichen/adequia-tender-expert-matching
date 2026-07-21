import { Info } from 'lucide-react';

import { Tooltip, TooltipContent, TooltipTrigger } from '@/common/components/ui/tooltip';

export function InfoTooltip({ text }: { text: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        {/* A plain <Info> SVG has no focus/keyboard semantics -- wrapping
            it in a real button makes the tooltip reachable by keyboard
            and screen readers, not just mouse hover. */}
        <button
          type="button"
          aria-label="More info"
          className="inline-flex rounded-sm text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Info className="size-3.5" />
        </button>
      </TooltipTrigger>
      <TooltipContent>{text}</TooltipContent>
    </Tooltip>
  );
}
