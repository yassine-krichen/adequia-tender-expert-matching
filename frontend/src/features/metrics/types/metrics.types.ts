// Mirrors backend/app/features/metrics/schemas.py field-for-field
// (including snake_case) since this is the raw GET /metrics response body,
// not a UI model.
export type MetricGroup = {
  status: 'available' | 'pending';
  values: Record<string, number | string> | null;
  dataset: string | null;
  sample_size: number | null;
  computed_at: string | null;
  note: string | null;
  pending_reason: string | null;
};

export type MetricsSnapshot = {
  extraction: MetricGroup;
  retrieval: MetricGroup;
  anomaly_detection: MetricGroup;
  guardrails: MetricGroup;
  scoring_agreement: MetricGroup;
  report_quality: MetricGroup;
  efficiency: MetricGroup;
};
