const SUGGESTIONS = [
  { icon: "🌍", label: "Compare countries", query: "Compare the full health profiles of France and Japan in 2019" },
  { icon: "📈", label: "Analyze trends", query: "How has life expectancy changed in Nigeria between 2015 and 2020?" },
  { icon: "🏥", label: "Explore health profiles", query: "What are all health indicators for Germany in 2020?" },
  { icon: "🏆", label: "Rank countries", query: "Rank the top 10 countries by hospital bed density in 2019" },
];

export default function EmptyState({ onSelect }) {
  return (
    <div className="empty-state">
      <p className="empty-tagline">
        Explore global health data using natural language.
      </p>
      <div className="suggestions">
        {SUGGESTIONS.map((s) => (
          <button key={s.label} className="suggestion-card" onClick={() => onSelect(s.query)}>
            <span className="suggestion-icon">{s.icon}</span>
            <span className="suggestion-label">{s.label}</span>
            <span className="suggestion-query">{s.query}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
