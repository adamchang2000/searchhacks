import {
  QUERY_CATEGORY_LABELS,
  QUERY_CATEGORY_PARENTS,
  QUERY_CATEGORY_PATHS,
  QueryCategory,
} from "@searchhacks/types/query-category";

const ROOT = QueryCategory.ALL_CATEGORIES;
const ALL = Object.values(QueryCategory) as QueryCategory[];

/** The 25 top-level categories (direct children of the root). */
export const TOP_LEVEL: QueryCategory[] = ALL.filter((c) =>
  QUERY_CATEGORY_PARENTS[c].includes(ROOT),
);

/**
 * Subcategories whose canonical path is exactly root > top > sub, i.e. that the optimizer
 * places at (top, sub) when given as override_query_category. Using only these keeps the
 * driver's view of a query's category identical to the server's.
 */
export function canonicalSubcategories(top: QueryCategory): QueryCategory[] {
  return ALL.filter((c) => {
    const path = QUERY_CATEGORY_PATHS[c];
    return path.length === 3 && path[1] === top && !TOP_LEVEL.includes(c);
  });
}

export function label(c: QueryCategory): string {
  return QUERY_CATEGORY_LABELS[c];
}
