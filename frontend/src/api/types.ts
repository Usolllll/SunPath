export type PriorityMode = "school" | "balanced" | "major";
export interface Weights {
  school: number;
  major: number;
  fit: number;
}
export interface PhysicalInfo {
  color_weak?: boolean;
  color_blind?: boolean;
  naked_vision?: number | null;
  corrected_vision?: number | null;
  hearing?: boolean;
  smell?: boolean;
  hbsag?: boolean;
}
export interface Profile {
  province: string;
  exam_year: number;
  score: number;
  rank: number;
  subjects: string[];
  regions: string[];
  majors: string[];
  // v2 决策维度（全部可选，缺省不改变一期行为）
  priority_mode?: PriorityMode;
  budget_total?: number | null;
  interests?: Partial<Record<"R" | "I" | "A" | "S" | "E" | "C", number>> | null;
  physical?: PhysicalInfo | null;
  intent_types?: string[] | null;
}
export interface User {
  id: number;
  email: string;
  name: string;
  profile: Profile | null;
}
export type Risk = "reach" | "steady" | "safe";
export interface University {
  id: number;
  name: string;
  city: string;
  region: string;
  level: string;
  category: string;
  description: string;
  initials: string;
  color: string;
  // v2 院校维度（未收录时为 null，不猜测）
  level_tier?: number | null;
  city_tier?: number | null;
  transfer_friendly?: number | null;
  transfer_notes?: string | null;
  transfer_year?: number | null;
  official_url?: string | null;
}
/** 四年总成本估算（学费 + 住宿费 + 城市等级生活费估算） */
export interface CostEstimate {
  tuition: number;
  accommodation: number;
  living: number;
  years: number;
  annual: number;
  total: number;
  note: string;
}
export interface Group {
  id: number;
  code: string;
  name: string;
  majors: string[];
  required_subjects: string[];
  tuition: number;
  university: University;
  province: string;
  year: number;
  seats: number;
  history: { year: number; score: number; rank: number }[];
  latest_rank: number | null;
  latest_score: number | null;
  data_label: string;
  risk?: Risk;
  baseline_rank?: number;
  history_rank_min?: number;
  history_rank_max?: number;
  rank_ratio?: number;
  volatility?: number;
  reasons?: string[];
  warnings?: string[];
  preference_matches?: number;
  // v2 成本与打分字段
  tuition_type?: string | null;
  accommodation?: number | null;
  duration_years?: number | null;
  major_category?: string | null;
  cost_year?: number | null;
  cost?: CostEstimate | null;
  school_score?: number | null;
  major_score?: number | null;
  rank_fit?: number | null;
  transfer_bonus?: number | null;
  total_score?: number | null;
  weights?: Weights | null;
}
export interface Plan {
  id: number;
  name: string;
  items: Group[];
  profile_snapshot: Profile;
  created_at: string;
  updated_at: string;
}
/** 一组候选的四年成本汇总（注意：/recommendations 的 total 是全部候选之和，不代表一份方案） */
export interface BudgetSummary {
  count: number;
  total: number;
  min: number;
  max: number;
  over_budget: number;
  budget?: number | null;
  usage?: number | null;
}
export interface Recommendation {
  items: Group[];
  counts: Record<Risk, number>;
  disclaimer: string;
  engine_version: string;
  mode?: PriorityMode;
  weights?: Weights;
  budget?: BudgetSummary;
  budget_cap?: number | null;
  ai_selection?: {
    model_label: string | null;
    skill: string;
    requested_count: number;
    selected_count: number;
    eligible_count: number;
    catalog_universities: number;
    catalog_groups: number;
    selected_universities: number;
    minimum_count: number;
    maximum_count: number;
    below_minimum: boolean;
    missing_tiers: Risk[];
    message: string;
  };
}
/** POST /recommendations/generate：按模式生成的冲稳保方案（1:2:1 配额） */
export interface GeneratedPlan extends Recommendation {
  missing_tiers: Risk[];
  message?: string;
}
export interface CompareSide {
  mode: PriorityMode;
  label: string;
  items: Group[];
  missing_tiers?: Risk[];
}
export interface CompareDiff {
  a_count: number;
  b_count: number;
  changed: number;
  added: number[];
  removed: number[];
  rank_delta: Record<string, number>;
  metric_delta: { school: number; major: number; rank_fit: number };
}
export interface RecommendationCompare {
  a: CompareSide;
  b: CompareSide;
  diff: CompareDiff;
  summary: string;
  weights: { a: Weights; b: Weights };
  disclaimer: string;
}
export interface Catalog {
  items: Group[];
  total: number;
  regions: string[];
  universities: CatalogUniversity[];
}
export interface CatalogUniversity extends University {
  group_ids: number[];
  group_count: number;
  location: {
    latitude: number;
    longitude: number;
    source_url: string;
    precision: string;
    label: string;
  } | null;
}
export interface MajorSummary {
  name: string;
  code: string;
  category: string;
  major_class: string;
  riasec_main: string[];
  as_of: string;
}
export interface MajorList {
  total: number;
  items: MajorSummary[];
  note?: string;
}
export interface MajorCard extends MajorSummary {
  study_what: string;
  fit_for: string;
  hard_where: string;
  career_where: string;
  riasec_secondary: string[];
  source: string;
  disclaimer: string;
}
export interface CoverageOption {
  subject: string;
  groups: number;
  gain: number;
}
export interface Coverage {
  chosen: string[];
  base_groups: number;
  options: CoverageOption[];
  disclaimer?: string;
}
export interface ReadinessBlocker {
  level: "red" | "yellow";
  label: string;
  condition: string;
  majors: string[];
  text: string;
  source?: string | null;
  source_url?: string | null;
}
export interface ReadinessTodo {
  type: string;
  window: string;
  source: string;
  source_url?: string | null;
  selected: boolean;
}
export interface Readiness {
  blockers: ReadinessBlocker[];
  warnings: ReadinessBlocker[];
  todos: ReadinessTodo[];
  version?: string;
  disclaimer: string;
  note?: string | null;
}
export interface BudgetEstimate {
  group_id: number;
  university: string;
  cost: CostEstimate;
  tier: string;
  budget_total?: number | null;
  over_budget: boolean;
  over_by: number;
  disclaimer: string;
}
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}
export interface ChatReply {
  content: string;
  model: string;
  model_label: string;
  finish_reason: string;
  context?: ChatContextSummary | null;
}
export interface ChatContextSummary {
  profile_included: boolean;
  saved_plans_enabled: boolean;
  total_saved_plans: number;
  requested_plan_count: number;
  included_plan_count: number;
  omitted_plan_count: number;
  plan_names: string[];
  max_plans: number;
}
export interface ChatAvailableContext {
  profile_available: boolean;
  saved_plan_count: number;
  max_plans: number;
  options_truncated: boolean;
  plans: {
    id: number;
    name: string;
    group_count: number;
    updated_at: string;
  }[];
}
