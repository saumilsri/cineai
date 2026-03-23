import { useCallback, useRef, useState } from "react";

interface Props {
  onSubmit: (video: File, prompt: string) => void;
  disabled: boolean;
}

export default function UploadZone({ onSubmit, disabled }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [prompt, setPrompt] = useState(
    "Make this faster paced and more engaging",
  );
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback((f: File) => {
    if (f.type.startsWith("video/")) setFile(f);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    [handleFile],
  );

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="text-center space-y-2">
        <h1 className="text-4xl font-bold tracking-tight">CineAI</h1>
        <p className="text-neutral-400">
          Drop a video. Describe how you want it edited. Get a better cut back.
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`
          flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed
          px-6 py-16 transition-colors
          ${dragOver ? "border-violet-500 bg-violet-500/10" : "border-neutral-700 hover:border-neutral-500 bg-neutral-900/50"}
          ${file ? "border-emerald-600 bg-emerald-900/10" : ""}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
          }}
        />
        {file ? (
          <div className="space-y-1 text-center">
            <p className="text-lg font-medium text-emerald-400">{file.name}</p>
            <p className="text-sm text-neutral-500">
              {(file.size / 1024 / 1024).toFixed(1)} MB — click to change
            </p>
          </div>
        ) : (
          <div className="space-y-1 text-center">
            <p className="text-lg text-neutral-300">
              Drop video here or click to browse
            </p>
            <p className="text-sm text-neutral-500">MP4, MOV, AVI, MKV</p>
          </div>
        )}
      </div>

      {/* Prompt */}
      <div>
        <label className="mb-1.5 block text-sm font-medium text-neutral-300">
          Edit instructions
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          className="w-full rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-3 text-sm
                     text-neutral-100 placeholder-neutral-500 outline-none transition
                     focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
          placeholder="e.g. Make this faster paced, remove dead air, add B-roll"
        />
      </div>

      {/* Submit */}
      <button
        onClick={() => file && onSubmit(file, prompt)}
        disabled={!file || disabled}
        className="w-full rounded-xl bg-violet-600 px-6 py-3.5 text-sm font-semibold text-white
                   transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {disabled ? "Processing..." : "Start Editing"}
      </button>
    </div>
  );
}
