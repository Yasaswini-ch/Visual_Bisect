import { useEffect, useRef } from "react";

function load(src: string): Promise<HTMLImageElement> {
  return new Promise((res, rej) => {
    const im = new Image();
    im.crossOrigin = "anonymous";
    im.onload = () => res(im);
    im.onerror = rej;
    im.src = src;
  });
}

/** Difference heatmap computed in the browser: changed pixels glow over a dimmed copy of the "after" image. */
export function Heatmap({ before, after }: { before: string; after: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    let alive = true;
    Promise.all([load(before), load(after)]).then(([a, b]) => {
      const c = ref.current;
      if (!alive || !c) return;
      const w = (c.width = b.naturalWidth), h = (c.height = b.naturalHeight);
      const ctx = c.getContext("2d", { willReadFrequently: true })!;
      const grab = (im: HTMLImageElement) => { ctx.clearRect(0, 0, w, h); ctx.drawImage(im, 0, 0, w, h); return ctx.getImageData(0, 0, w, h); };
      const da = grab(a), db = grab(b);
      const out = ctx.createImageData(w, h);
      for (let i = 0; i < db.data.length; i += 4) {
        const d = (Math.abs(da.data[i] - db.data[i]) + Math.abs(da.data[i + 1] - db.data[i + 1]) + Math.abs(da.data[i + 2] - db.data[i + 2])) / 3;
        const hot = d > 12;
        out.data[i] = hot ? 255 : db.data[i] * 0.3;
        out.data[i + 1] = hot ? Math.max(40, 200 - d * 2) : db.data[i + 1] * 0.3;
        out.data[i + 2] = hot ? 40 : db.data[i + 2] * 0.3;
        out.data[i + 3] = 255;
      }
      ctx.putImageData(out, 0, 0);
    }).catch(() => {});
    return () => { alive = false; };
  }, [before, after]);
  return <canvas ref={ref} className="w-full rounded-lg border border-line" />;
}
