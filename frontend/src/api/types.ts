export interface Profile {
  province: string;
  exam_year: number;
  score: number;
  rank: number;
  subjects: string[];
  regions: string[];
  majors: string[];
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
}
export interface Plan {
  id: number;
  name: string;
  items: Group[];
  profile_snapshot: Profile;
  created_at: string;
  updated_at: string;
}
export interface Recommendation {
  items: Group[];
  counts: Record<Risk, number>;
  disclaimer: string;
  engine_version: string;
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
