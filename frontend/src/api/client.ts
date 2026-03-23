export interface JobProgress {
  status: string;
  progress: number;
  message: string;
  output_video?: string;
  moments?: Moment[];
  edit_plan?: EditPlan;
  error?: string;
}

export interface Moment {
  start: number;
  end: number;
  description: string;
  energy: "low" | "medium" | "high";
  type: "content" | "dead_air" | "transition" | "highlight";
}

export interface EditPlan {
  cuts: { start: number; end: number; reason: string }[];
  broll_insertions: {
    insert_at: number;
    duration: number;
    search_query: string;
    source: string;
  }[];
  music: {
    track: string;
    volume: number;
    fade_in: number;
    fade_out: number;
  };
}

export interface MusicTrack {
  name: string;
  filename: string;
}

export async function createJob(
  video: File,
  prompt: string,
): Promise<string> {
  const form = new FormData();
  form.append("video", video);
  form.append("prompt", prompt);

  const res = await fetch("/api/jobs", { method: "POST", body: form });
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
  const data = await res.json();
  return data.job_id;
}

export function streamProgress(
  jobId: string,
  onUpdate: (data: JobProgress) => void,
  onError: (err: string) => void,
): () => void {
  const es = new EventSource(`/api/jobs/${jobId}/stream`);

  es.onmessage = (event) => {
    try {
      const data: JobProgress = JSON.parse(event.data);
      onUpdate(data);
      if (data.status === "done" || data.status === "failed") {
        es.close();
      }
    } catch {
      onError("Failed to parse progress update");
    }
  };

  es.onerror = () => {
    onError("Connection lost");
    es.close();
  };

  return () => es.close();
}

export async function fetchMusicTracks(): Promise<MusicTrack[]> {
  const res = await fetch("/api/music");
  if (!res.ok) return [];
  const data = await res.json();
  return data.tracks ?? [];
}
