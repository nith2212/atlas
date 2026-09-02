import { useEffect, useState } from "react";
import IndicatorDetailsModal from "./IndicatorDetailsModal";

const API_URL = import.meta.env.VITE_API_URL;

export default function CategoryBrowser({ onSelect }) {
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [indicators, setIndicators] = useState([]);
  const [status, setStatus] = useState("loading");
  const [indicatorStatus, setIndicatorStatus] = useState("idle");
  const [selectedIndicator, setSelectedIndicator] = useState(null);

  useEffect(() => {
    fetch(`${API_URL}/categories`)
      .then((response) => {
        if (!response.ok) throw new Error("Unable to load categories");
        return response.json();
      })
      .then((data) => {
        setCategories(data.categories || []);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  const selectCategory = async (category) => {
    setSelectedCategory(category);
    setIndicators([]);
    setIndicatorStatus("loading");

    try {
      const response = await fetch(
        `${API_URL}/categories/${encodeURIComponent(category)}/indicators?limit=8`
      );
      if (!response.ok) throw new Error("Unable to load indicators");
      const data = await response.json();
      setIndicators(data.indicators || []);
      setIndicatorStatus("ready");
    } catch {
      setIndicatorStatus("error");
    }
  };

  return (
    <section className="category-browser" aria-labelledby="category-browser-title">
      <div className="category-heading">
        <div>
          <p className="section-label">Explore the catalog</p>
          <h2 id="category-browser-title">Browse by category</h2>
        </div>
        <span className="category-count">
          {status === "ready" ? `${categories.length} buckets` : "WHO indicators"}
        </span>
      </div>

      {status === "loading" && <p className="category-message">Loading categories...</p>}
      {status === "error" && (
        <p className="category-message category-message--error">
          Categories are unavailable right now. You can still search with the query bar.
        </p>
      )}
      {status === "ready" && (
        <div className="category-grid">
          {categories.map(({ category, count }) => (
            <button
              key={category}
              className={`category-card ${selectedCategory === category ? "is-selected" : ""}`}
              onClick={() => selectCategory(category)}
              aria-pressed={selectedCategory === category}
            >
              <span className="category-card-name">{category}</span>
              <span className="category-card-count">{count} indicators</span>
            </button>
          ))}
        </div>
      )}

      {selectedCategory && (
        <div className="category-indicators">
          <div className="category-indicators-heading">
            <span>{selectedCategory}</span>
            <span className="category-indicators-hint">Select an indicator to analyse</span>
          </div>
          {indicatorStatus === "loading" && <p className="category-message">Loading indicators...</p>}
          {indicatorStatus === "error" && (
            <p className="category-message category-message--error">Unable to load indicators.</p>
          )}
          {indicatorStatus === "ready" && (
            <div className="indicator-list">
              {indicators.map((indicator) => (
                <button
                  key={indicator.code}
                  className="indicator-list-item"
                  onClick={() => setSelectedIndicator(indicator)}
                >
                  <span>{indicator.name}</span>
                  <span className="indicator-list-unit">{indicator.unit || "View data"}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      {selectedIndicator && (
        <IndicatorDetailsModal
          indicator={selectedIndicator}
          onClose={() => setSelectedIndicator(null)}
          onSubmit={(query) => {
            setSelectedIndicator(null);
            onSelect(query);
          }}
        />
      )}
    </section>
  );
}
