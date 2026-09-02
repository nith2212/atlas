export default function ResultsView({ result }) {
  const { query, answer, streaming, activities, elapsed, evidence = [] } = result;
  const toolCount = activities.filter((a) => a.name !== "Answer generated").length;
  const hasEvidence = evidence.length > 0;

  return (
    <div className="results fade-in">

      <section className="result-section">
        <div className="section-label">Question</div>
        <p className="result-query">{query}</p>
      </section>

      {activities.length > 0 && streaming && (
        <>
          <div className="section-divider" />
          <section className="result-section">
            <div className="section-label">Agent Activity</div>
            <ul className="activity-steps">
              {activities.map((a, i) => (
                <li key={`${a.name}-${i}`} className={`activity-step ${a.status}`}>
                  <span className="step-icon">
                    {a.status === "loading" ? <span className="spinner" /> : a.status === "done" ? "✓" : "·"}
                  </span>
                  <span className="step-name">{a.name}{a.count > 1 ? ` ×${a.count}` : ""}</span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}

      <div className="section-divider" />

      <section className="result-section answer-section">
        <div className="section-label">Answer</div>
        <p className="result-answer">
          {answer || <span className="muted">Generating...</span>}
          {streaming && answer && <span className="cursor" />}
        </p>
        {!streaming && !hasEvidence && (
          <div className="info-banner">No evidence was returned for this query.</div>
        )}
        {elapsed && (
          <div className="elapsed">{toolCount} tool{toolCount !== 1 ? "s" : ""} · {elapsed}s</div>
        )}
      </section>

      {activities.length > 0 && !streaming && (
        <>
          <div className="section-divider" />
          <section className="result-section">
            <div className="section-label">Agent Activity</div>
            <ul className="activity-steps">
              {activities.map((a, i) => (
                <li key={`${a.name}-${i}`} className={`activity-step ${a.status}`}>
                  <span className="step-icon">✓</span>
                  <span className="step-name">{a.name}{a.count > 1 ? ` ×${a.count}` : ""}</span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}

    </div>
  );
}
