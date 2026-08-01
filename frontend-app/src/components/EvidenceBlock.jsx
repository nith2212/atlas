const fmt = (n) => Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });

const TREND_LABELS = {
  improving:          { label: "Improving",          color: "#2d7a4f" },
  declining:          { label: "Declining",          color: "#b94040" },
  volatile:           { label: "Volatile",           color: "#a06020" },
  stable:             { label: "Stable",             color: "#575799" },
  insufficient_data:  { label: "Insufficient data",  color: "#9D9DCC" },
};

function PercentileBadge({ value }) {
  return (
    <span className="percentile-badge" title="Health percentile — higher is always healthier">
      {value}th
    </span>
  );
}

function TrendPill({ trend }) {
  const t = TREND_LABELS[trend] ?? { label: trend, color: "#9D9DCC" };
  return (
    <span className="trend-pill" style={{ color: t.color, borderColor: t.color }}>
      {t.label}
    </span>
  );
}

function InsightLine({ label, value }) {
  return (
    <div className="insight-line">
      <span className="insight-label">{label}</span>
      <span className="insight-value">{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------

function ProfileCard({ data }) {
  return (
    <div className="evidence-block">
      <div className="evidence-header">
        <div className="evidence-tool-name">get_country_health_profile()</div>
        <div className="evidence-subtitle">{data.country} · {data.year}</div>
      </div>
      <table className="evidence-table">
        <thead>
          <tr><th>Indicator</th><th>Value</th><th>Unit</th><th>Percentile</th></tr>
        </thead>
        <tbody>
          {data.metrics.map((m, i) =>
            m.missing ? (
              <tr key={i}>
                <td>{m.label}</td>
                <td colSpan={3} className="unit-cell">no data</td>
              </tr>
            ) : (
              <tr key={i}>
                <td>{m.label}</td>
                <td>{fmt(m.value)}</td>
                <td className="unit-cell">{m.unit}</td>
                <td><PercentileBadge value={m.health_percentile} /></td>
              </tr>
            )
          )}
        </tbody>
      </table>
      {(data.strongest_indicator || data.weakest_indicator) && (
        <div className="insight-row">
          {data.strongest_indicator && (
            <InsightLine label="Strongest" value={data.strongest_indicator.replace(/_/g, " ")} />
          )}
          {data.weakest_indicator && (
            <InsightLine label="Weakest" value={data.weakest_indicator.replace(/_/g, " ")} />
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function ComparisonCard({ data }) {
  const [ca, cb] = data.countries;
  return (
    <div className="evidence-block">
      <div className="evidence-header">
        <div className="evidence-tool-name">compare_countries()</div>
        <div className="evidence-subtitle">{ca} vs {cb} · {data.year}</div>
      </div>
      <table className="evidence-table">
        <thead>
          <tr><th>Indicator</th><th>{ca}</th><th>{cb}</th><th>Gap</th><th>Leader</th></tr>
        </thead>
        <tbody>
          {data.comparisons.map((c, i) =>
            c.missing ? (
              <tr key={i}>
                <td>{c.label}</td>
                <td colSpan={4} className="unit-cell">incomplete data</td>
              </tr>
            ) : (
              <tr key={i}>
                <td>{c.label}</td>
                <td>
                  {fmt(c[ca].value)}
                  <span className="unit-cell"> {c.unit}</span>
                  <br />
                  <PercentileBadge value={c[ca].health_percentile} />
                </td>
                <td>
                  {fmt(c[cb].value)}
                  <span className="unit-cell"> {c.unit}</span>
                  <br />
                  <PercentileBadge value={c[cb].health_percentile} />
                </td>
                <td className="unit-cell">{fmt(c.difference)}</td>
                <td className="leader-cell">{c.leader}</td>
              </tr>
            )
          )}
        </tbody>
      </table>
      {data.largest_gap_indicator && (
        <div className="insight-row">
          <InsightLine
            label="Largest gap"
            value={data.largest_gap_indicator.replace(/_/g, " ")}
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function RankingCard({ data }) {
  const s = data.global_stats;
  return (
    <div className="evidence-block">
      <div className="evidence-header">
        <div className="evidence-tool-name">rank_countries_by_indicator()</div>
        <div className="evidence-subtitle">{data.indicator} · {data.year}</div>
      </div>
      <table className="evidence-table">
        <thead>
          <tr><th>#</th><th>Country</th><th>Value</th><th>Percentile</th></tr>
        </thead>
        <tbody>
          {data.ranks.map((r) => (
            <tr key={r.rank}>
              <td className="rank-cell">{r.rank}</td>
              <td>{r.country}</td>
              <td>{fmt(r.value)} <span className="unit-cell">{r.unit}</span></td>
              <td><PercentileBadge value={r.health_percentile} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      {s && (
        <div className="insight-row">
          <InsightLine label="Global mean"   value={`${fmt(s.mean)} ${data.unit}`} />
          <InsightLine label="Global median" value={`${fmt(s.median)} ${data.unit}`} />
          <InsightLine label="Std dev"       value={fmt(s.stdev)} />
          <InsightLine label="Countries"     value={s.n} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function TrendCard({ data }) {
  return (
    <div className="evidence-block">
      <div className="evidence-header">
        <div className="evidence-tool-name">get_health_trend()</div>
        <div className="evidence-subtitle">
          {data.country} · {data.indicator} · {data.pct_change > 0 ? "+" : ""}{data.pct_change}% overall
        </div>
      </div>
      <div className="trend-header-row">
        <TrendPill trend={data.trend} />
        {data.best_outcome_year && (
          <InsightLine label="Best year"  value={data.best_outcome_year} />
        )}
        {data.worst_outcome_year && (
          <InsightLine label="Worst year" value={data.worst_outcome_year} />
        )}
      </div>
      <table className="evidence-table">
        <thead>
          <tr><th>Year</th><th>Value</th><th>YoY change</th></tr>
        </thead>
        <tbody>
          {data.points.map((p, i) => {
            const yoy = data.yoy?.find((y) => y.to_year === p.year);
            return (
              <tr key={i}>
                <td>{p.year}</td>
                <td>{fmt(p.value)} <span className="unit-cell">{data.unit}</span></td>
                <td className={yoy ? (yoy.change > 0 ? "yoy-pos" : "yoy-neg") : "unit-cell"}>
                  {yoy ? `${yoy.change > 0 ? "+" : ""}${fmt(yoy.change)}` : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------

function RawCard({ data }) {
  return (
    <div className="evidence-block">
      <div className="evidence-header">
        <div className="evidence-tool-name">raw result</div>
      </div>
      <p className="raw-text">{data.text}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------

export default function EvidenceBlock({ data }) {
  switch (data.type) {
    case "profile":    return <ProfileCard data={data} />;
    case "comparison": return <ComparisonCard data={data} />;
    case "ranking":    return <RankingCard data={data} />;
    case "trend":      return <TrendCard data={data} />;
    default:           return <RawCard data={data} />;
  }
}
