import { useCallback, useState } from "react";
import { createJob, streamProgress, type JobProgress } from "./api/client";
import UploadZone from "./components/UploadZone";
import ProcessingView from "./components/ProcessingView";
import ResultView from "./components/ResultView";

type Phase = "upload" | "processing" | "done" | "error";

export default function App() {
  const [phase, setPhase] = useState<Phase>("upload");
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState<JobProgress>({
    status: "pending",
    progress: 0,
    message: "",
  });
  const [error, setError] = useState("");

  const handleSubmit = useCallback(async (video: File, prompt: string) => {
    try {
      setPhase("processing");
      setError("");

      const id = await createJob(video, prompt);
      setJobId(id);

      streamProgress(
        id,
        (data) => {
          setProgress(data);
          if (data.status === "done") setPhase("done");
          if (data.status === "failed") {
            setPhase("error");
            setError(data.error ?? "Unknown error");
          }
        },
        (err) => {
          setPhase("error");
          setError(err);
        },
      );
    } catch (e: unknown) {
      setPhase("error");
      setError(e instanceof Error ? e.message : "Upload failed");
    }
  }, []);

  const handleReset = useCallback(() => {
    setPhase("upload");
    setJobId("");
    setProgress({ status: "pending", progress: 0, message: "" });
    setError("");
  }, []);

  return (
    <div className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="border-b border-neutral-800 px-6 py-4">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <span className="text-lg font-bold tracking-tight">
            <span className="text-violet-400">Cine</span>AI
          </span>
          <span className="text-xs text-neutral-600">v0.1 prototype</span>
        </div>
      </header>

      {/* Main content */}
      <main className="flex flex-1 items-center justify-center px-6 py-12">
        {phase === "upload" && (
          <UploadZone onSubmit={handleSubmit} disabled={false} />
        )}

        {phase === "processing" && <ProcessingView progress={progress} />}

        {phase === "done" && (
          <ResultView
            progress={progress}
            jobId={jobId}
            onReset={handleReset}
          />
        )}

        {phase === "error" && (
          <div className="mx-auto max-w-md space-y-4 text-center">
            <h2 className="text-xl font-bold text-red-400">
              Something went wrong
            </h2>
            <p className="text-sm text-neutral-400">{error}</p>
            <button
              onClick={handleReset}
              className="rounded-xl border border-neutral-700 px-6 py-3 text-sm font-medium
                         text-neutral-300 transition hover:bg-neutral-800"
            >
              Try Again
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
