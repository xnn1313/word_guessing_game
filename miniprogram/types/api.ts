export interface GuessItem {
  word: string;
  similarity: number;
}

export interface DisplayGuessItem extends GuessItem {
  displaySimilarity: string;
  tone: "high" | "mid" | "low" | "zero";
  latest?: boolean;
}

export interface GameState {
  session_id: string;
  attempts: number;
  history: GuessItem[];
  correct_count: number;
  game_active: boolean;
  mode: "classic" | "campaign";
  campaign_level_id?: string | null;
}

export interface AuthPayload {
  authenticated: boolean;
  username: string;
  token: string;
  expires_in_days: number;
  game: GameState;
}

export interface CampaignLevel {
  id: string;
  name: string;
  order: number;
  category_id: string;
  category_name: string;
  category_emoji: string;
  difficulty: number;
  difficulty_label: string;
  unlocked: boolean;
  stars: number;
  best_attempts: number | null;
}

export interface CampaignCategory {
  id: string;
  name: string;
  emoji: string;
  description: string;
  stars: number;
  max_stars: number;
  levels: CampaignLevel[];
  expanded?: boolean;
}

export interface CampaignCatalog {
  total_stars: number;
  max_stars: number;
  categories: CampaignCategory[];
}

export interface CampaignResult {
  level_id: string;
  stars: number;
  earned_stars: number;
  best_attempts: number;
  total_stars: number;
  next_level: CampaignLevel | null;
}

export interface GuessResponse {
  session_id: string;
  similarity: number;
  is_correct: boolean;
  attempts: number;
  history: GuessItem[];
  correct_count: number;
  target_word?: string;
  message: string;
  campaign_result?: CampaignResult;
}

export interface BattlePlayer {
  username: string;
  is_self: boolean;
  is_host: boolean;
  is_winner: boolean;
  attempts: number;
  best_similarity: number;
  rematch_ready: boolean;
  displayBest?: string;
  roleText?: string;
}

export interface BattleState {
  code: string;
  state: "waiting" | "playing" | "finished";
  is_host: boolean;
  can_start: boolean;
  duration_seconds: number;
  remaining_seconds: number;
  players: BattlePlayer[];
  my_history: GuessItem[];
  winner_username: string | null;
  finish_reason: string | null;
  can_rematch: boolean;
  rematch_ready: boolean;
  target_word?: string;
  guess_result?: {
    word: string;
    similarity: number;
    is_correct: boolean;
    in_word_bank: boolean;
  };
}
