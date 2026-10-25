/** Marks closer than this many pixels share one marker, so markers never overlap. */
export const GROUP_PX = 22;

/**
 * Splits moments, in time order, into the markers drawn on a rail `width`
 * pixels wide. A marker sits at its first moment; the next one starts at
 * least GROUP_PX later. Before the rail is measured, every moment is its own.
 */
export function groupMarks<T extends { at_seconds: number }>(moments: T[], duration: number, width: number): T[][] {
  const x = (seconds: number) => (Math.min(seconds, duration) / duration) * width;
  const groups: T[][] = [];
  for (const moment of [...moments].sort((a, b) => a.at_seconds - b.at_seconds)) {
    const last = groups.at(-1);
    if (last && width > 0 && duration > 0 && x(moment.at_seconds) - x(last[0].at_seconds) < GROUP_PX) last.push(moment);
    else groups.push([moment]);
  }
  return groups;
}
