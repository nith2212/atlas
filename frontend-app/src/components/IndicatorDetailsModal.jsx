import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL;

export default function IndicatorDetailsModal({ indicator, onClose, onSubmit }) {
  const [details, setDetails] = useState(null);
  const [status, setStatus] = useState("loading");
  const [country, setCountry] = useState("");
  const [year, setYear] = useState("");

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    fetch(`${API_URL}/indicators/${encodeURIComponent(indicator.code)}`)
      .then((response) => {
        if (!response.ok) throw new Error("Unable to load indicator details");
        return response.json();
      })
      .then((data) => {
        if (data.error) throw new Error(data.error);
        setDetails(data);
        const countries = data.coverage?.countries || [];
        setCountry(countries[0] || "");
        setYear(data.coverage?.max_year || "");
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [indicator.code, onClose]);

  const coverage = details?.coverage || {};
  const canSubmit = country && year && status === "ready";

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="indicator-modal" role="dialog" aria-modal="true" aria-labelledby="indicator-modal-title">
        <div className="modal-header">
          <div>
            <p className="section-label">Indicator details</p>
            <h2 id="indicator-modal-title">{indicator.name}</h2>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close indicator details">×</button>
        </div>

        {status === "loading" && <p className="category-message">Loading availability...</p>}
        {status === "error" && (
          <p className="category-message category-message--error">This indicator could not be loaded.</p>
        )}
        {status === "ready" && (
          <>
            <p className="indicator-description">{details.description}</p>
            <dl className="indicator-meta">
              <div><dt>Unit</dt><dd>{details.unit}</dd></div>
              <div><dt>Coverage</dt><dd>{coverage.country_count} countries, {coverage.min_year}–{coverage.max_year}</dd></div>
              <div><dt>Data type</dt><dd>{details.data_type === "categorical" ? "Status or category" : "Numeric"}</dd></div>
              {details.data_type === "categorical" && (
                <div><dt>Observed values</dt><dd>{details.values.join(", ")}</dd></div>
              )}
            </dl>
            <div className="indicator-form">
              <label>
                Country
                <select value={country} onChange={(event) => setCountry(event.target.value)}>
                  {coverage.countries.map((code) => <option key={code} value={code}>{code}</option>)}
                </select>
              </label>
              <label>
                Year
                <input type="number" min={coverage.min_year || 1900} max={coverage.max_year || new Date().getFullYear()} value={year} onChange={(event) => setYear(event.target.value)} />
              </label>
            </div>
            <div className="modal-actions">
              <button className="modal-secondary" onClick={onClose}>Cancel</button>
              <button
                className="modal-primary"
                disabled={!canSubmit}
                onClick={() => onSubmit(
                  details.data_type === "categorical"
                    ? `What is the status for ${details.name} in ${country} in ${year}?`
                    : `Show ${details.name} for ${country} in ${year}`
                )}
              >View data</button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}