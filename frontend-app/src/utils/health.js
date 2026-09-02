// Single source of truth for health-percentile color mapping — every chart
// pulls fill/stroke colors from these functions, never a hardcoded palette.

export const HEALTH_COLORS = {
  strong: "#A1BC98",
  mid: "#CDC1FF",
  weak: "#E6B2BA",
  missing: "#C9C5C0",
};

/** percentile: 0-100, or null/undefined for missing data. Higher is always healthier. */
export function getHealthColor(percentile) {
  if (percentile === null || percentile === undefined) return HEALTH_COLORS.missing;
  if (percentile >= 66) return HEALTH_COLORS.strong;
  if (percentile >= 34) return HEALTH_COLORS.mid;
  return HEALTH_COLORS.weak;
}

/** Trend line color — same shared tokens, keyed by trend classification instead of a number. */
export function getTrendColor(trend) {
  switch (trend) {
    case "improving": return HEALTH_COLORS.strong;
    case "declining": return HEALTH_COLORS.weak;
    case "stable":    return HEALTH_COLORS.mid;
    default:          return HEALTH_COLORS.missing; // volatile / insufficient_data
  }
}
