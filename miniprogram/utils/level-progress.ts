import type { ExtraLevelCatalog, PuzzleDifficulty } from "../types/api";

type ExtraGameKey = "sokoban" | "arrow_maze";
type StoredProgress = Partial<Record<PuzzleDifficulty, Record<string, number>>>;

const storageKey = (gameKey: ExtraGameKey) => `extra-level-progress:${gameKey}:v1`;

function loadProgress(gameKey: ExtraGameKey): StoredProgress {
  try {
    const value = wx.getStorageSync(storageKey(gameKey));
    return value && typeof value === "object" ? value as StoredProgress : {};
  } catch {
    return {};
  }
}

export function completeGuestLevel(
  gameKey: ExtraGameKey,
  difficulty: PuzzleDifficulty,
  levelOrder: number,
  stars: number,
): void {
  const progress = loadProgress(gameKey);
  const difficultyProgress = { ...(progress[difficulty] || {}) };
  difficultyProgress[String(levelOrder)] = Math.max(
    Number(difficultyProgress[String(levelOrder)] || 0),
    Number(stars || 1),
  );
  progress[difficulty] = difficultyProgress;
  try {
    wx.setStorageSync(storageKey(gameKey), progress);
  } catch {
    // Storage failure must not block the completed-game result.
  }
}

export function mergeGuestLevelProgress(
  catalog: ExtraLevelCatalog,
  gameKey: ExtraGameKey,
): ExtraLevelCatalog {
  const progress = loadProgress(gameKey);
  let totalStars = 0;
  const difficulties = catalog.difficulties.map((group) => {
    const difficultyProgress = progress[group.key] || {};
    let previousCompleted = true;
    let completedLevels = 0;
    const levels = group.levels.map((level) => {
      const stars = Math.max(Number(level.stars || 0), Number(difficultyProgress[String(level.order)] || 0));
      const unlocked = level.order === 1 || previousCompleted;
      previousCompleted = stars > 0;
      if (stars > 0) {
        completedLevels += 1;
        totalStars += stars;
      }
      return { ...level, stars, unlocked };
    });
    return { ...group, completed_levels: completedLevels, levels };
  });
  return { ...catalog, total_stars: totalStars, difficulties };
}
