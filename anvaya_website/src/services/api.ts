const BASE_URL = "/api";

export interface JobStatus {
  job_id: string;
  status: "queued" | "extracting" | "building" | "rendering" | "completed" | "failed";
  step: number;
  message: string;
  error: string | null;
  filename: string;
}

export interface Segment {
  title: string;
  order: number;
  narration_script: string;
  narration_clean: string;
  start_time: number;
  timestamp: string;
  duration: number;
}

export interface JobResult {
  job_id: string;
  paper_title: string;
  video_url: string;
  segments: Segment[];
  transcript: string;
}

export async function uploadPDF(file: File): Promise<{ job_id: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE_URL}/generate`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail ?? "Upload failed");
  }
  return res.json();
}

export async function pollStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${BASE_URL}/status/${jobId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Status check failed" }));
    throw new Error(err.detail ?? "Status check failed");
  }
  return res.json();
}

export async function getResult(jobId: string): Promise<JobResult> {
  const res = await fetch(`${BASE_URL}/result/${jobId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Result fetch failed" }));
    throw new Error(err.detail ?? "Result fetch failed");
  }
  return res.json();
}

export function videoURL(jobId: string): string {
  return `${BASE_URL}/video/${jobId}`;
}
