import {
  QUERY_CATEGORY_LABELS,
  QUERY_CATEGORY_PARENTS,
  QueryCategory,
} from "@searchhacks/types/query-category";

const labels = QUERY_CATEGORY_LABELS as Record<number, string>;

export function categoryLabel(id: number | null | undefined): string | null {
  return id == null ? null : (labels[id] ?? `#${id}`);
}

/** The 25 level-1 categories (direct children of the root), sorted by label. */
export const TOP_LEVEL_CATEGORIES: { id: number; label: string }[] = Object.entries(
  QUERY_CATEGORY_PARENTS as Record<number, readonly number[]>,
)
  .filter(([, parents]) => parents.includes(QueryCategory.ALL_CATEGORIES))
  .map(([id]) => ({ id: Number(id), label: labels[Number(id)] }))
  .sort((a, b) => a.label.localeCompare(b.label));

/** Value of the category filter that selects unclassified searches. */
export const UNCLASSIFIED = -1;
