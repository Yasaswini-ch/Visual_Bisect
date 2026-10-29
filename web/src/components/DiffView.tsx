import { useEffect, useState } from "react";
import { html } from "diff2html";
import { ColorSchemeType } from "diff2html/lib/types";
import "diff2html/bundles/css/diff2html.min.css";

export function DiffView({ url }: { url: string }) {
  const [out, setOut] = useState<string>("");
  const [err, setErr] = useState(false);
  useEffect(() => {
    fetch(url).then((r) => (r.ok ? r.text() : Promise.reject())).then((t) =>
      setOut(html(t, { drawFileList: false, matching: "lines", outputFormat: "line-by-line", colorScheme: ColorSchemeType.DARK })),
    ).catch(() => setErr(true));
  }, [url]);
  if (err) return <div className="text-sm text-dim">No diff recorded for this run.</div>;
  return <div className="rounded-lg overflow-hidden border border-line text-sm" dangerouslySetInnerHTML={{ __html: out }} />;
}
