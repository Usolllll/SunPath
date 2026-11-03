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
}
export interface Catalog {
  items: Group[];
  total: number;
  regions: string[];
}
