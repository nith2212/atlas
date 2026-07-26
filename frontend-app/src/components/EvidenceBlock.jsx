function ProfileCard({ data }) {
  return (
    <div className="evidence-block">
      <div className="evidence-tool-name">get_country_health_profile()</div>
      <div className="evidence-subtitle">{data.country} · {data.year}</div>
      <table className="evidence-table">
        <thead>
          <tr><th>Indicator</th><th>Value</th><th>Unit</th></tr>
        </thead>
        <tbody>
          {data.metrics.map((m, i) => (
            <tr key={i}>
              <td>{m.label}</td>
              <td>{Number(m.value).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
              <td className="unit-cell">{m.unit}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ComparisonCard({ data }) {
  return (
    <div className="evidence-block">
      <div className="evidence-tool-name">compare_countries()</div>
      <div className="evidence-subtitle">{data.indicator} · {data.year}</div>
      <table className="evidence-table">
        <thead>
          <tr><th>Country</th><th>Value</th><th>Unit</th></tr>
        </thead>
        <tbody>
          {data.values.map((v, i) => (
            <tr key={i}>
              <td>{v.country}</td>
              <td>{Number(v.value).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
              <td className="unit-cell">{data.unit}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RankingCard({ data }) {
  return (
    <div className="evidence-block">
      <div className="evidence-tool-name">rank_countries_by_indicator()</div>
      <div className="evidence-subtitle">{data.indicator} · {data.year}</div>
      <table className="evidence-table">
        <thead>
          <tr><th>#</th><th>Country</th><th>Value</th><th>Unit</th></tr>
        </thead>
        <tbody>
          {data.ranks.map((r) => (
            <tr key={r.rank}>
              <td className="rank-cell">{r.rank}</td>
              <td>{r.country}</td>
              <td>{Number(r.value).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
              <td className="unit-cell">{data.unit}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TrendCard({ data }) {
  return (
    <div className="evidence-block">
      <div className="evidence-tool-name">get_health_trend()</div>
      <div className="evidence-subtitle">{data.country} · {data.indicator} · {data.pct_change > 0 ? "+" : ""}{data.pct_change}% change</div>
      <table className="evidence-table">
        <thead>
          <tr><th>Year</th><th>Value</th><th>Unit</th></tr>
        </thead>
        <tbody>
          {data.points.map((p, i) => (
            <tr key={i}>
              <td>{p.year}</td>
              <td>{Number(p.value).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
              <td className="unit-cell">{data.unit}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RawCard({ data }) {
  return (
    <div className="evidence-block">
      <div className="evidence-tool-name">raw result</div>
      <p className="raw-text">{data.text}</p>
    </div>
  );
}

export default function EvidenceBlock({ data }) {
  switch (data.type) {
    case "profile":    return <ProfileCard data={data} />;
    case "comparison": return <ComparisonCard data={data} />;
    case "ranking":    return <RankingCard data={data} />;
    case "trend":      return <TrendCard data={data} />;
    default:           return <RawCard data={data} />;
  }
}
