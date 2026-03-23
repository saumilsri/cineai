import type { JobProgress, Moment } from "../api/client";

interface Props {
  progress: JobProgress;
  jobId: string;
  onReset: () => void;
}

function fmt(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function ResultView({ progress, jobId, onReset }: Props) {
  const videoUrl = progress.output_video;
  const plan = progress.edit_plan;

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div className="text-center space-y-1">
        <h2 className="text-2xl font-bold text-emerald-400">Edit Complete</h2>
        <p className="text-sm text-neutral-400">
          Your video has been processed. Review and download below.
        </p>
      </div>

      {/* Video player */}
      {videoUrl && (
        <div className="overflow-hidden rounded-2xl border border-neutral-800 bg-black">
          <video
            src={videoUrl}
            controls
            className="w-full"
          />
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        <a
          href={`/api/jobs/${jobId}/download`}
          className="flex-1 rounded-xl bg-violet-600 px-6 py-3 text-center text-sm font-semibold
                     text-white transition hover:bg-violet-500"
        >
          Download Video
        </a>
        <button
          onClick={onReset}
          className="rounded-xl border border-neutral-700 px-6 py-3 text-sm font-medium
                     text-neutral-300 transition hover:bg-neutral-800"
        >
          Edit Another
        </button>
      </div>

      {/* Edit summary */}
      {plan && (
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4">
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
              Cuts Made
            </h4>
            {plan.cuts.length === 0 ? (
              <p className="text-sm text-neutral-500">None</p>
            ) : (
              <ul className="space-y-1">
                {plan.cuts.map((c, i) => (
                  <li key={i} className="text-sm text-neutral-300">
                    <span className="font-mono text-xs text-red-400">
                      {fmt(c.start)}–{fmt(c.end)}
                    </span>{" "}
                    <span className="text-neutral-500">{c.reason}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4">
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
              B-Roll Added
            </h4>
            {plan.broll_insertions.length === 0 ? (
              <p className="text-sm text-neutral-500">None</p>
            ) : (
              <ul className="space-y-1">
                {plan.broll_insertions.map((b, i) => (
                  <li key={i} className="text-sm text-neutral-300">
                    <span className="font-mono text-xs text-blue-400">
                      @{fmt(b.insert_at)}
                    </span>{" "}
                    <span className="text-neutral-500">
                      {b.search_query} ({b.duration}s)
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4">
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
              Music
            </h4>
            <p className="text-sm text-neutral-300">
              {plan.music.track}
            </p>
            <p className="text-xs text-neutral-500">
              Vol: {Math.round(plan.music.volume * 100)}% | Fade:
              {plan.music.fade_in}s in, {plan.music.fade_out}s out
            </p>
          </div>
        </div>
      )}

      {/* Moments timeline */}
      {progress.moments && progress.moments.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-neutral-300">
            Moment Breakdown
          </h3>
          <div className="max-h-72 space-y-1.5 overflow-y-auto rounded-xl border border-neutral-800 bg-neutral-900/50 p-4">
            {progress.moments.map((m: Moment, i: number) => (
              <div key={i} className="flex items-start gap-3 text-sm">
                <span className="shrink-0 rounded bg-neutral-800 px-2 py-0.5 font-mono text-xs text-neutral-400">
                  {fmt(m.start)}–{fmt(m.end)}
                </span>
                <span
                  className={`
                    ${m.type === "dead_air" ? "text-red-400 line-through" : ""}
                    ${m.type === "highlight" ? "text-amber-400" : ""}
                    ${m.type === "content" ? "text-neutral-300" : ""}
                    ${m.type === "transition" ? "text-blue-400" : ""}
                  `}
                >
                  {m.description}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
