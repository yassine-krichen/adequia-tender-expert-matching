// Judgment-call brackets — copy style intentionally kept, thresholds can be
// retuned. Only meant to give the raw candidate/TDR counts on the workspace
// dashboard a sense of scale, not a precise statistic.
export function describePoolSize(count: number): string {
  if (count === 0) return 'no candidates yet';
  if (count <= 10) return 'boutique-sized pool';
  if (count <= 50) return 'startup-sized pool';
  if (count <= 250) return 'SME-sized pool';
  return 'enterprise-sized pool';
}

export function describeTdrVolume(count: number): string {
  if (count === 0) return 'no TDRs yet';
  if (count <= 5) return 'early-stage pipeline';
  if (count <= 20) return 'active pipeline';
  if (count <= 75) return 'high-volume pipeline';
  return 'enterprise-scale pipeline';
}
