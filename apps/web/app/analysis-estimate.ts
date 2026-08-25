export const MIN_ANALYSIS_BYTES = 1024 * 1024;

export type AnalysisEstimate = {
  analysisBytes: number;
  fraction: number;
  likelySeconds: number;
  lowSeconds: number;
  highSeconds: number;
};

// Conservative initial calibration. The API can replace this with observed
// throughput once enough completed runs exist.
const BYTES_PER_SECOND = {
  cdn: 5 * 1024 * 1024,
  origin: 3 * 1024 * 1024,
} as const;

export function clampAnalysisBytes(requested: number, fileSize: number): number {
  if (!Number.isFinite(requested) || fileSize <= 0) return 0;
  return Math.min(fileSize, Math.max(Math.min(MIN_ANALYSIS_BYTES, fileSize), Math.round(requested)));
}

export function estimateAnalysis(
  sourceType: "cdn" | "origin",
  fileSize: number,
  requestedBytes: number,
): AnalysisEstimate {
  const analysisBytes = clampAnalysisBytes(requestedBytes, fileSize);
  const likelySeconds = analysisBytes ? Math.max(60, Math.ceil(analysisBytes / BYTES_PER_SECOND[sourceType])) : 0;
  return {
    analysisBytes,
    fraction: fileSize > 0 ? analysisBytes / fileSize : 0,
    likelySeconds,
    lowSeconds: likelySeconds ? Math.max(30, Math.floor(likelySeconds * 0.7)) : 0,
    highSeconds: likelySeconds ? Math.ceil(likelySeconds * 1.8) : 0,
  };
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.max(0, Math.round(seconds))} sec`;
  const minutes = Math.ceil(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = minutes / 60;
  return `${hours < 10 ? hours.toFixed(1) : Math.ceil(hours)} hr`;
}
