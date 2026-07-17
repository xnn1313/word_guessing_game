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

export type PuzzleGameKey = "word" | "sudoku" | "idiom" | "memory";
export type PuzzleDifficulty = "easy" | "medium" | "hard";
export type PuzzleRunMode = "daily" | "practice" | "level";
export type MemoryTheme =
  | "classic"
  | "fruit"
  | "animal"
  | "transport"
  | "food"
  | "weather"
  | "sport"
  | "ocean"
  | "space"
  | "place"
  | "music"
  | "culture";

export interface GameOverviewItem {
  key: PuzzleGameKey;
  title: string;
  availability: "available" | "coming_soon" | "maintenance";
  progress_text: string;
  progress_percent: number;
  best_score: number | null;
  daily_completed: boolean;
  last_played_at: string | null;
}

export interface GamesOverview {
  server_date: string;
  summary: {
    available_games: number;
    completed_today: number;
    total_stars: number;
    last_game_key: PuzzleGameKey | null;
  };
  games: GameOverviewItem[];
}

export interface SudokuSavedState {
  grid: string;
  notes: Record<string, number[]>;
  elapsed_seconds: number;
  hints_used: number;
  mistakes: number;
}

export interface SudokuPuzzleResponse {
  puzzle_id: string;
  mode: "daily" | "practice";
  puzzle_date: string | null;
  difficulty: PuzzleDifficulty;
  givens: string;
  run_id: string | null;
  saved_state: SudokuSavedState | null;
  limits: { max_hints: number };
}

export interface IdiomCell {
  row: number;
  column: number;
  type: "fixed" | "input";
  value?: string;
}

export interface IdiomEntry {
  id: string;
  direction: "across" | "down";
  start: { row: number; column: number };
  length: number;
  clue: string;
  pinyin_hint: string;
}

export interface IdiomLevel {
  id: string;
  order: number;
  title: string;
  difficulty: PuzzleDifficulty;
  unlocked: boolean;
  stars: number;
  best_score: number | null;
}

export interface IdiomCategory {
  id: string;
  name: string;
  description: string;
  completed_levels: number;
  total_levels: number;
  levels: IdiomLevel[];
}

export interface IdiomCatalog {
  total_stars: number;
  max_stars: number;
  categories: IdiomCategory[];
}

export interface IdiomSavedState {
  grid: string[];
  elapsed_seconds: number;
  hints_used: number;
  mistakes: number;
}

export interface IdiomPuzzleResponse {
  puzzle_id: string;
  mode: "daily" | "level";
  puzzle_date: string | null;
  title: string;
  difficulty: PuzzleDifficulty;
  size: number;
  cells: IdiomCell[];
  entries: IdiomEntry[];
  character_bank: string[];
  run_id: string | null;
  saved_state: IdiomSavedState | null;
  limits: { max_hints: number };
}

export interface MemoryCard {
  position: number;
  face_key: string;
  display: string;
}

export interface MemorySavedState {
  matched_positions: number[];
  moves: number;
  elapsed_seconds: number;
}

export interface MemoryBoardResponse {
  board_id: string;
  mode: "daily" | "practice";
  puzzle_date: string | null;
  difficulty: PuzzleDifficulty;
  theme: MemoryTheme;
  rows: number;
  columns: number;
  cards: MemoryCard[];
  run_id: string | null;
  saved_state: MemorySavedState | null;
}

export interface PuzzleHintResponse {
  index?: number;
  row: number;
  column: number;
  value: string | number;
  hints_used: number;
  remaining_hints: number;
}

export interface PuzzleCompletionResult {
  score: number;
  stars: number;
  elapsed_seconds: number;
  mistakes?: number;
  hints_used?: number;
  moves?: number;
  earned_stars?: number;
  total_stars?: number;
  next_level_id?: string | null;
  is_new_best: boolean;
}

export interface PuzzleSubmitResponse {
  correct: boolean;
  status: "completed" | "incorrect";
  invalid_cells?: number[];
  unmatched_count?: number;
  result?: PuzzleCompletionResult;
}
