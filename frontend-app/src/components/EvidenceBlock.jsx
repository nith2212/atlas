import { RadialBarChart, RadialBar, PolarAngleAxis } from "recharts";
import { getHealthColor } from "../utils/health";

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

function PercentileRing({ metric, isStrongest, isWeakest }) {
  const wrapperClass = [
    "ring-item",
    isStrongest && "ring-strongest",
    isWeakest && "ring-weakest",
  ].filter(Boolean).join(" ");

  return (
    <div className={wrapperClass} title={metric.label}>
      <div className="ring-chart">
        {metric.missing ? (
          <div className="ring-missing" />
        ) : (
          <RadialBarChart
            width={64}
            height={64}
            cx="50%"
            cy="50%"
            innerRadius="72%"
            outerRadius="100%"
            data={[{ value: metric.health_percentile }]}
            startAngle={90}
            endAngle={-270}
          >
            <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
            <RadialBar
              background={{ fill: "var(--border)" }}
              dataKey="value"
              cornerRadius={6}
              fill={getHealthColor(metric.health_percentile)}
              isAnimationActive
            />
          </RadialBarChart>
        )}
        <span className="ring-value">
          {metric.missing ? "—" : `${metric.health_percentile}`}
        </span>
      </div>
      <span className="ring-label">{metric.label}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------

function ProfileCard({ data }) {
  const visibleMetrics = data.metrics.filter((m) => !m.missing);
  const strongestLabel = visibleMetrics.length
    ? visibleMetrics.reduce((best, current) =>
        current.health_percentile > best.health_percentile ? current : best
      ).label
    : null;
  const weakestLabel = visibleMetrics.length
    ? visibleMetrics.reduce((worst, current) =>
        current.health_percentile < worst.health_percentile ? current : worst
      ).label
    : null;

  return (
    <div className="evidence-block">
      <div className="evidence-header">
        <div className="evidence-tool-name">get_country_health_profile()</div>
        <div className="evidence-subtitle">{data.country} · {data.year}</div>
      </div>
      {visibleMetrics.length === 0 ? (
        <div className="insight-row">
          <InsightLine label="Status" value="No data available" />
        </div>
      ) : (
        <>
          <div className="percentile-ring-grid">
            {visibleMetrics.map((m, i) => (
              <PercentileRing
                key={i}
                metric={m}
                isStrongest={m.label === strongestLabel}
                isWeakest={m.label === weakestLabel}
              />
            ))}
          </div>
          <table className="evidence-table">
            <thead>
              <tr><th>Indicator</th><th>Value</th><th>Unit</th><th>Percentile</th></tr>
            </thead>
            <tbody>
              {visibleMetrics.map((m, i) => (
                <tr key={i}>
                  <td>{m.label}</td>
                  <td>{fmt(m.value)}</td>
                  <td className="unit-cell">{m.unit}</td>
                  <td><PercentileBadge value={m.health_percentile} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {(strongestLabel || weakestLabel) && (
            <div className="insight-row">
              {strongestLabel && (
                <InsightLine label="Strongest" value={strongestLabel} />
              )}
              {weakestLabel && (
                <InsightLine label="Weakest" value={weakestLabel} />
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function ComparisonCard({ data }) {
  const [ca, cb] = data.countries;
  const visibleComparisons = (data.comparisons || []).filter((c) => !c.missing);

  return (
    <div className="evidence-block">
      <div className="evidence-header">
        <div className="evidence-tool-name">compare_countries()</div>
        <div className="evidence-subtitle">{ca} vs {cb} · {data.year}</div>
      </div>
      {visibleComparisons.length === 0 ? (
        <div className="insight-row">
          <InsightLine label="Status" value="No comparison data available" />
        </div>
      ) : (
        <>
          <table className="evidence-table">
            <thead>
              <tr><th>Indicator</th><th>{ca}</th><th>{cb}</th><th>Gap</th><th>Leader</th></tr>
            </thead>
            <tbody>
              {visibleComparisons.map((c, i) => (
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
              ))}
            </tbody>
          </table>
          {data.largest_gap_indicator && (
            <div className="insight-row">
              <InsightLine
                label="Largest gap"
                value={data.largest_gap_indicator}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function RankingCard({ data }) {
  const s = data.global_stats;
  const visibleRanks = (data.ranks || []).filter((r) => r && r.value != null);

  return (
    <div className="evidence-block">
      <div className="evidence-header">
        <div className="evidence-tool-name">rank_countries_by_indicator()</div>
        <div className="evidence-subtitle">{data.indicator} · {data.year}</div>
      </div>
      {visibleRanks.length === 0 ? (
        <div className="insight-row">
          <InsightLine label="Status" value="No ranking data available" />
        </div>
      ) : (
        <>
          <table className="evidence-table">
            <thead>
              <tr><th>#</th><th>Country</th><th>Value</th><th>Percentile</th></tr>
            </thead>
            <tbody>
              {visibleRanks.map((r) => (
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
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function TrendCard({ data }) {
  const visiblePoints = (data.points || []).filter((p) => p && p.value != null);

  return (
    <div className="evidence-block">
      <div className="evidence-header">
        <div className="evidence-tool-name">get_health_trend()</div>
        <div className="evidence-subtitle">
          {data.country} · {data.indicator} · {data.pct_change > 0 ? "+" : ""}{data.pct_change}% overall
        </div>
      </div>
      {visiblePoints.length === 0 ? (
        <div className="insight-row">
          <InsightLine label="Status" value="No trend data available" />
        </div>
      ) : (
        <>
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
              {visiblePoints.map((p, i) => {
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
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function SearchCard({ data }) {
  return (
    <div className="evidence-block">
      <div className="evidence-header">
        <div className="evidence-tool-name">search_indicators()</div>
        <div className="evidence-subtitle">"{data.query}"</div>
      </div>
      <table className="evidence-table">
        <thead>
          <tr><th>Indicator</th><th>Category</th><th>Unit</th></tr>
        </thead>
        <tbody>
          {data.results.map((r, i) => (
            <tr key={i}>
              <td>{r.name}</td>
              <td className="unit-cell">{r.category || "—"}</td>
              <td className="unit-cell">{r.unit || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------

function CategoryBrowserCard({ data }) {
  return (
    <div className="evidence-block">
      <div className="evidence-header">
        <div className="evidence-tool-name">browse_categories()</div>
        <div className="evidence-subtitle">WHO indicator buckets</div>
      </div>
      <table className="evidence-table">
        <thead>
          <tr><th>Category</th><th>Indicators</th></tr>
        </thead>
        <tbody>
          {data.categories.map((c, i) => (
            <tr key={i}>
              <td>{c.category}</td>
              <td className="unit-cell">{c.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------

function CategoricalResultCard({ data }) {
  return (
    <div className="evidence-block">
      <div className="evidence-header">
        <div className="evidence-tool-name">get_indicator_value()</div>
        <div className="evidence-subtitle">{data.country} · {data.year}</div>
      </div>
      <div className="categorical-result">
        <div className="categorical-result-label">{data.indicator}</div>
        <div className="categorical-result-value">{data.value}</div>
      </div>
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
    case "profile":          return <ProfileCard data={data} />;
    case "comparison":       return <ComparisonCard data={data} />;
    case "ranking":          return <RankingCard data={data} />;
    case "trend":            return <TrendCard data={data} />;
    case "indicator_search": return <SearchCard data={data} />;
    case "category_browser": return <CategoryBrowserCard data={data} />;
    case "categorical_result": return <CategoricalResultCard data={data} />;
    default:                 return <RawCard data={data} />;
  }
}
