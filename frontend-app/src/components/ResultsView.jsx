import EvidenceBlock from "./EvidenceBlock";

export default function ResultsView({ result }) {
  const { query, answer, streaming, activities, evidence, elapsed } = result;
  const toolCount = activities.filter((a) => a.name !== "Answer generated").length;

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
                <li key={i} className={`activity-step ${a.status}`}>
                  <span className="step-icon">
                    {a.status === "loading" ? <span className="spinner" /> : "✓"}
                  </span>
                  <span className="step-name">{a.name}()</span>
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
        {elapsed && (
          <div className="elapsed">{toolCount} tool{toolCount !== 1 ? "s" : ""} · {elapsed}s</div>
        )}
      </section>

      {evidence.length > 0 && (
        <>
          <div className="section-divider" />
          <section className="result-section">
            <div className="section-label">Evidence</div>
            <div className="evidence-tables">
              {evidence.map((ev, i) => (
                <EvidenceBlock key={i} data={ev} />
              ))}
            </div>
          </section>
        </>
      )}

      {activities.length > 0 && !streaming && (
        <>
          <div className="section-divider" />
          <section className="result-section">
            <div className="section-label">Agent Activity</div>
            <ul className="activity-steps">
              {activities.map((a, i) => (
                <li key={i} className={`activity-step ${a.status}`}>
                  <span className="step-icon">✓</span>
                  <span className="step-name">{a.name}()</span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}

    </div>
  );
}
