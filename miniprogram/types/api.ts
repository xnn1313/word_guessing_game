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

export type PuzzleGameKey =
  | "word"
  | "sudoku"
  | "idiom"
  | "memory"
  | "word_search"
  | "poetry"
  | "sokoban"
  | "arrow_maze";
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
    daily_total: number;
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
  daily_slot: number | null;
  daily_count: number;
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

export type WordSearchTheme = "classic" | "nature" | "animals" | "character" | "emotion";

export interface WordSearchPathCell {
  row: number;
  column: number;
}

export interface WordSearchThemeItem {
  key: WordSearchTheme;
  title: string;
  description: string;
}

export interface WordSearchThemeCatalog {
  themes: WordSearchThemeItem[];
  difficulties: Array<{
    key: PuzzleDifficulty;
    rows: number;
    columns: number;
    word_count: number;
  }>;
}

export interface WordSearchEntry {
  id: string;
  clue: string;
  length: number;
}

export interface WordSearchSavedState {
  found_entry_ids: string[];
  found_paths: WordSearchPathCell[][];
  elapsed_seconds: number;
  mistakes: number;
}

export interface WordSearchBoardResponse {
  board_id: string;
  mode: "daily" | "practice";
  puzzle_date: string | null;
  difficulty: PuzzleDifficulty;
  theme: WordSearchTheme;
  theme_title: string;
  rows: number;
  columns: number;
  word_count: number;
  grid: string[][];
  entries: WordSearchEntry[];
  run_id: string | null;
  saved_state: WordSearchSavedState | null;
}

export interface WordSearchSubmitResponse {
  correct: boolean;
  status: "playing" | "completed" | "incorrect";
  code?: string;
  mistakes?: number;
  found_entry_ids?: string[];
  found_count?: number;
  remaining_count?: number;
  result?: PuzzleCompletionResult;
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
  pushes?: number;
  optimal_steps?: number;
  correct_count?: number;
  total_questions?: number;
  earned_stars?: number;
  total_stars?: number;
  next_level_id?: string | null;
  level_order?: number;
  next_level_order?: number | null;
  is_new_best: boolean;
}

export interface PoetryQuestion {
  id: string;
  type: "next" | "previous" | "author" | "title" | "dynasty";
  prompt: string;
  context: string;
  options: string[];
  index: number;
  total: number;
}

export interface PoetrySavedState {
  question_index: number;
  correct_count: number;
  elapsed_seconds: number;
  hints_used: number;
  mistakes: number;
}

export interface PoetryQuizResponse {
  puzzle_id: string;
  mode: "daily" | "practice";
  puzzle_date: string | null;
  difficulty: PuzzleDifficulty;
  question_count: number;
  catalog_size: number;
  rotation_days: number;
  question: PoetryQuestion;
  run_id: string | null;
  saved_state: PoetrySavedState | null;
}

export interface PoetryStudyNote {
  source: string;
  excerpt: string;
  meaning: string;
  key_terms: string;
}

export interface PoetryAnswerResponse {
  correct: boolean;
  status: "playing" | "completed";
  correct_answer?: string;
  explanation?: string;
  study?: PoetryStudyNote;
  correct_count?: number;
  mistakes?: number;
  next_question?: PoetryQuestion;
  result?: PuzzleCompletionResult;
}

export interface SokobanSavedState {
  history: string;
  elapsed_seconds: number;
  hints_used: number;
  mistakes: number;
}

export interface SokobanBoardResponse {
  puzzle_id: string;
  mode: "daily" | "level" | "practice";
  puzzle_date: string | null;
  difficulty: PuzzleDifficulty;
  level_order: number | null;
  level_count: number | null;
  rows: number;
  columns: number;
  board: string[];
  box_count: number;
  par_pushes: number;
  run_id: string | null;
  saved_state: SokobanSavedState | null;
}

export interface ArrowMazeSavedState {
  path: number[];
  elapsed_seconds: number;
  hints_used: number;
  mistakes: number;
}

export interface ArrowMazeBoardResponse {
  puzzle_id: string;
  mode: "daily" | "level" | "practice";
  puzzle_date: string | null;
  difficulty: PuzzleDifficulty;
  level_order: number | null;
  level_count: number | null;
  rows: number;
  columns: number;
  grid: string[];
  start_index: number;
  target_index: number;
  optimal_steps: number;
  run_id: string | null;
  saved_state: ArrowMazeSavedState | null;
}

export interface ExtraLevelItem {
  order: number;
  puzzle_id: string;
  unlocked: boolean;
  stars: number;
  best_score: number | null;
}

export interface ExtraLevelDifficulty {
  key: PuzzleDifficulty;
  completed_levels: number;
  total_levels: number;
  levels: ExtraLevelItem[];
}

export interface ExtraLevelCatalog {
  game_key: "sokoban" | "arrow_maze";
  total_stars: number;
  max_stars: number;
  difficulties: ExtraLevelDifficulty[];
}

export interface PuzzleSubmitResponse {
  correct: boolean;
  status: "completed" | "incorrect" | "playing";
  invalid_cells?: number[];
  unmatched_count?: number;
  result?: PuzzleCompletionResult;
}
