import { useEffect, useState } from "react";

/** Reveals text word by word when `animate` is set; otherwise shows it at once. */
export function Typewriter({ text, animate }: { text: string; animate: boolean }) {
  const words = text.split(" ");
  const [n, setN] = useState(animate ? 0 : words.length);
  useEffect(() => {
    if (!animate) { setN(words.length); return; }
    setN(0);
    const id = setInterval(() => setN((k) => {
      if (k >= words.length) { clearInterval(id); return k; }
      return k + 1;
    }), 45);
    return () => clearInterval(id);
  }, [text, animate]); // eslint-disable-line react-hooks/exhaustive-deps
  return <>{words.slice(0, n).join(" ")}</>;
}
