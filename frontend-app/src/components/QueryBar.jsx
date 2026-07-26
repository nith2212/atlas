import { useState, useEffect } from "react";

const PLACEHOLDERS = [
  "Compare India and Japan by life expectancy in 2019...",
  "Show hospital bed trends in Nigeria from 2015 to 2020...",
  "Rank the top 5 countries by air pollution in 2019...",
  "Which country had the highest NCD mortality in 2020?",
  "Compare full health profiles of France and Mexico in 2019...",
];

export default function QueryBar({ onSend, isLoading }) {
  const [input, setInput] = useState("");
  const [placeholderIdx, setPlaceholderIdx] = useState(0);

  useEffect(() => {
    const id = setInterval(
      () => setPlaceholderIdx((i) => (i + 1) % PLACEHOLDERS.length),
      3000
    );
    return () => clearInterval(id);
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSend(input.trim());
    setInput("");
  };

  return (
    <form className="query-bar" onSubmit={handleSubmit}>
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder={PLACEHOLDERS[placeholderIdx]}
        disabled={isLoading}
        autoFocus
      />
      <button type="submit" disabled={isLoading || !input.trim()}>
        {isLoading ? <span className="btn-spinner" /> : "Analyse →"}
      </button>
    </form>
  );
}
