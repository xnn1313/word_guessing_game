import type { DisplayGuessItem, GuessItem } from "../types/api";

export function similarityTone(value: number): DisplayGuessItem["tone"] {
  if (value === 0) return "zero";
  if (value >= 50) return "high";
  if (value >= 25) return "mid";
  return "low";
}

export function decorateHistory(
  history: GuessItem[] = [],
  sortMode: "similarity" | "time" = "time",
): DisplayGuessItem[] {
  const latestIndex = history.length - 1;
  const items = history.map((item, index) => ({
    ...item,
    displaySimilarity: `${Number(item.similarity).toFixed(4)}%`,
    tone: similarityTone(Number(item.similarity)),
    latest: index === latestIndex,
    _index: index,
  }));
  if (sortMode === "similarity") {
    items.sort((a, b) => b.similarity - a.similarity);
  } else {
    items.reverse();
  }
  return items;
}
