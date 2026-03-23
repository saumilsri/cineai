import type { JobProgress, Moment } from "../api/client";

const STEPS = [
  { key: "extracting", label: "Extracting frames & audio" },
  { key: "transcribing", label: "Transcribing speech" },
  { key: "analyzing", label: "Analyzing with VLM" },
  { key: "planning", label: "Planning edits" },
  { key: "fetching_broll", label: "Fetching B-roll" },
  { key: "rendering", label: "Rendering final video" },
];

interface Props {
  progress: JobProgress;
}

function fmt(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function ProcessingView({ progress }: Props) {
  const currentIdx = STEPS.findIndex((s) => s.key === progress.status);

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div className="text-center space-y-1">
        <h2 className="text-2xl font-bold">Processing</h2>
        <p className="text-neutral-400 text-sm">{progress.message}</p>
      </div>

      {/* Progress bar */}
      <div className="space-y-2">
        <div className="h-2 w-full overflow-hidden rounded-full bg-neutral-800">
          <div
            className="h-full rounded-full bg-violet-500 transition-all duration-500"
            style={{ width: `${progress.progress}%` }}
          />
        </div>
        <p className="text-right text-xs text-neutral-500">
          {progress.progress}%
        </p>
      </div>

      {/* Step list */}
      <div className="space-y-2">
        {STEPS.map((step, i) => {
          let state: "done" | "active" | "pending" = "pending";
          if (i < currentIdx) state = "done";
          else if (i === currentIdx) state = "active";

          return (
            <div
              key={step.key}
              className={`flex items-center gap-3 rounded-lg px-4 py-2.5 text-sm transition
                ${state === "active" ? "bg-violet-500/10 text-violet-300" : ""}
                ${state === "done" ? "text-neutral-500" : ""}
                ${state === "pending" ? "text-neutral-600" : ""}
              `}
            >
              <span className="flex h-6 w-6 items-center justify-center">
                {state === "done" && (
                  <svg
                    className="h-4 w-4 text-emerald-500"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={3}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                )}
                {state === "active" && (
                  <span className="h-2 w-2 animate-pulse rounded-full bg-violet-400" />
                )}
                {state === "pending" && (
                  <span className="h-2 w-2 rounded-full bg-neutral-700" />
                )}
              </span>
              <span>{step.label}</span>
            </div>
          );
        })}
      </div>

      {/* Moments preview */}
      {progress.moments && progress.moments.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-neutral-300">
            Moments Detected
          </h3>
          <div className="max-h-64 space-y-1.5 overflow-y-auto rounded-xl border border-neutral-800 bg-neutral-900/50 p-4">
            {progress.moments.map((m: Moment, i: number) => (
              <div key={i} className="flex items-start gap-3 text-sm">
                <span className="mt-0.5 shrink-0 rounded bg-neutral-800 px-2 py-0.5 font-mono text-xs text-neutral-400">
                  {fmt(m.start)}
                </span>
                <span
                  className={`
                  ${m.type === "dead_air" ? "text-red-400" : ""}
                  ${m.type === "highlight" ? "text-amber-400" : ""}
                  ${m.type === "content" ? "text-neutral-300" : ""}
                  ${m.type === "transition" ? "text-blue-400" : ""}
                `}
                >
                  {m.description}
                </span>
                <span
                  className={`ml-auto shrink-0 rounded-full px-2 py-0.5 text-xs
                  ${m.energy === "high" ? "bg-amber-900/40 text-amber-400" : ""}
                  ${m.energy === "medium" ? "bg-neutral-800 text-neutral-400" : ""}
                  ${m.energy === "low" ? "bg-red-900/30 text-red-400" : ""}
                `}
                >
                  {m.energy}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
