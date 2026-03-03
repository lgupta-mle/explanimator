import type { JobResult } from "@/services/api";

const STORAGE_KEY = "anvaya_videos";

export interface SavedVideo {
  job_id: string;
  paper_title: string;
  date: string;
  duration_seconds: number;
  segments_count: number;
  difficulty?: string;
}

export function saveVideo(jobId: string, result: JobResult): void {
  const existing = loadVideos();
  const alreadySaved = existing.some((v) => v.job_id === jobId);
  if (alreadySaved) return;

  const totalDuration = result.segments.reduce((acc, s) => acc + (s.duration ?? 0), 0);
  
  // Map difficulty to display label
  const difficultyLabel = result.difficulty === "easy" ? "Initiate" : result.difficulty === "medium" ? "Scholar" : "";
  const displayTitle = difficultyLabel ? `${result.paper_title} (${difficultyLabel})` : result.paper_title;

  const entry: SavedVideo = {
    job_id: jobId,
    paper_title: displayTitle,
    date: new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }),
    duration_seconds: totalDuration,
    segments_count: result.segments.length,
    difficulty: result.difficulty,
  };

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([entry, ...existing]));
  } catch {
    // localStorage may be unavailable
  }
}

export function loadVideos(): SavedVideo[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as SavedVideo[];
  } catch {
    return [];
  }
}

export function deleteVideo(jobId: string): void {
  try {
    const existing = loadVideos();
    const updated = existing.filter((v) => v.job_id !== jobId);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch {
    // localStorage may be unavailable
  }
}

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
