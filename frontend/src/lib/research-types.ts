export interface ResearchArtifact { id: string; name: string; url: string; sha256: string; size_bytes?: number; media_type?: string }
export interface SeriesPoint { time: string; value: number }
export interface NumericSeries { source: string; entity: string; metric: string; unit: string; points: SeriesPoint[]; baseline_days: number; coverage_pct?: number; status: string; latest: number; expected: number | null; z_score: number | null }
export interface ForecastMetric { mae: number; rmse: number; samples?: number }
export interface Evaluation {
  forecast_metrics: Record<string, ForecastMetric>;
  interval_observed_coverage?: number;
  interval_nominal_coverage?: number;
  split?: { training: number; test: number };
  horizon_metrics?: Record<string, ForecastMetric | { forecast_metrics: Record<string, ForecastMetric> }>;
  by_horizon?: Record<string, Record<string, ForecastMetric>>;
  interval_coverage_by_horizon?: Record<string, number | null>;
  training_observations?: number;
  test_observations?: number;
  limitations?: string[];
}
export interface DomainForecast {
  domain: string; source: string; entity: string; metric: string; unit: string | null;
  status: string; method: string; history: SeriesPoint[];
  points: { time: string; value: number; low: number; high: number }[];
  evaluation: Evaluation | null; limitations: string[]; artifacts?: ResearchArtifact[];
  message?: string;
}
export interface StudyCase {
  id: string; title: string; dataset_mode: 'historical' | 'synthetic'; status: string;
  event_start: string; event_end: string; domains: string[]; region: string;
  description: string; provenance_url: string | null; limitations: string[];
  download_supported?: boolean; cadence_hours?: number; samples?: number;
  artifacts?: ResearchArtifact[];
}
export interface BenchmarkComparison {
  method: string; precision: number | null; recall: number | null;
  false_alerts: number; mean_detection_delay_hours: number | null;
  f1?: number; true_positives?: number; false_positives?: number; false_negatives?: number;
}
export interface BenchmarkScenario { id?: string; name?: string; title?: string; description?: string; domains?: string[]; comparisons?: (Omit<BenchmarkComparison, 'mean_detection_delay_hours'> & { detection_delay_hours?: number | null })[]; weather_associated_hours?: number; missing_hours?: number; [key: string]: unknown }
export interface SyntheticCaseData { id: string; dataset_mode: string; kind: string; traffic: number[]; weather: number[]; transit: number[]; quality: boolean[]; labels: boolean[]; onset_index: number | null }
export interface HistoricalChannel { id: string; label: string; unit: string; domain: string; values: (number | null)[]; provenance_url?: string }
export interface HistoricalProvenance { name?: string; source?: string; url?: string; provenance_url?: string; retrieved_at?: string; sha256?: string }
export interface HistoricalCaseData {
  id: string; dataset_mode: 'historical'; cadence_hours: number; times: string[];
  channels: HistoricalChannel[]; labels: boolean[]; label_definition: string; label_kind?: string;
  provenance: HistoricalProvenance[]; limitations: string[]; evaluation?: HistoricalCaseEvaluation | null;
}
export interface HistoricalCaseEvaluation {
  id?: string; case_id: string; dataset_mode: 'historical'; dataset_hash: string; method_version: string;
  training_observations: number; calibration_observations: number; test_observations: number;
  split_time: string; split?: { training: number; calibration: number; test: number };
  detection: { status: string; label_definition: string; label_kind: string; comparisons: {
    method: string; precision: number | null; recall: number | null; f1: number | null;
    false_alerts: number; mean_detection_delay_hours: number | null; samples: number; event_recall?: number | null;
  }[] };
  forecast: { status?: string; message?: string; target: string; unit: string; horizon_hours?: number; forecast_metrics: Record<string, ForecastMetric>;
    by_horizon?: Record<string, Record<string, ForecastMetric>>; interval_nominal_coverage?: number | null; interval_observed_coverage?: number | null;
    predictions?: { origin_index: number; target_index: number; horizon_hours: number; actual: number; value: number; low: number; high: number }[] };
  advance_warning: { status: string; message: string; target: string; horizon_hours: number;
    brier_score?: number | null; reference_brier_score?: number | null; brier_skill_score?: number | null;
    threshold?: number | null; precision?: number | null; recall?: number | null; mean_warning_lead_hours?: number | null;
    event_onsets?: number; events_with_advance_warning?: number; false_warning_hours?: number;
    comparisons?: { method: string; brier_score: number; precision: number | null; recall: number | null }[];
    predictions?: { time: string; index: number; probability: number; outcome: boolean }[] };
  limitations: string[]; artifacts?: ResearchArtifact[];
}
export interface ExperimentRun extends Partial<Evaluation> {
  id: string; source?: string; metric?: string; created_at?: string;
  dataset_mode?: string; dataset_hash: string; seed?: number; method_version?: string;
  anomaly_counts?: Record<string, number>; ground_truth_metrics?: unknown;
  comparisons?: BenchmarkComparison[]; scenarios?: BenchmarkScenario[];
  limitations: string[]; artifacts?: ResearchArtifact[];
}
export interface ResearchAsset {
  id: string; name: string; asset_type?: string; type?: string;
  geometry?: unknown; properties?: Record<string, unknown>; properties_json?: Record<string, unknown>;
  provenance_url?: string; dataset_mode?: string; available_at?: string;
}
export interface Exposure {
  asset_id: string; name: string; hazard_source: string; hazard_kind: string;
  relation: string; observed_at: string; provenance_url?: string;
  limitations: string[]; kind?: string; dataset_mode?: string; asset_type?: string;
}
