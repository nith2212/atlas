const SUGGESTIONS = [
  { icon: "🌍", label: "Compare countries", query: "Compare the full health profiles of France and Japan in 2019" },
  { icon: "📈", label: "Analyze trends", query: "How has life expectancy changed in Nigeria between 2015 and 2020?" },
];

import CategoryBrowser from "./CategoryBrowser";

export default function EmptyState({ onSelect, children }) {
  return (
    <div className="empty-state">
      <p className="empty-tagline">
        Explore global health data using natural language.
      </p>
      {children}
      <div className="empty-exploration">
        <CategoryBrowser onSelect={onSelect} />
        <aside className="suggestions" aria-labelledby="suggestions-title">
          <p className="section-label" id="suggestions-title">Suggested analyses</p>
          {SUGGESTIONS.map((s) => (
            <button key={s.label} className="suggestion-card" onClick={() => onSelect(s.query)}>
              <span className="suggestion-icon">{s.icon}</span>
              <span className="suggestion-label">{s.label}</span>
              <span className="suggestion-query">{s.query}</span>
            </button>
          ))}
        </aside>
      </div>
    </div>
  );
}
