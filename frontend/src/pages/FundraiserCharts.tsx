// v1.6.0 CR-033: fundraiser charts - cumulative income vs expenses (event dates marked) and income vs expenses donut.
// Same palette and conventions as the dashboard charts (income = slot 1 blue, expense = slot 2 orange).
import { Bar, BarChart, Cell, Legend, Line, LineChart, Pie, PieChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import { money } from "../api";
import { axisProps, CHROME, ChartCard, compact, DataTable, Masonry, SERIES, tooltipStyle, useNarrow } from "./Charts";

const DAY = 86400000;
const ts = (iso: string) => Date.parse(`${iso}T00:00:00Z`);
const dateFmt = (t: number) => new Date(t).toISOString().slice(0, 10);

export default function FundraiserCharts({ f, theme }: { f: any; theme: "light" | "dark" }) {
  const narrow = useNarrow(900);
  const s = SERIES[theme];
  const c = CHROME[theme];
  const tt = tooltipStyle(theme);
  const ax = axisProps(theme);
  const moneyFmt = (v: any) => money(String(v));

  const rows = f.cumulative.map((p: any) => ({ t: ts(p.date), income: Number(p.income), expense: Number(p.expense), net: Number(p.net) }));
  const evStart = ts(f.start_date);
  const evEnd = ts(f.end_date) + DAY;
  const first = Math.min(rows[0]?.t ?? evStart, evStart);
  const lastT = Math.max(rows[rows.length - 1]?.t ?? evEnd, evEnd);
  const pad = Math.max(2 * DAY, (lastT - first) * 0.06); // room so the event band and late steps are not on the edge
  const lo = first - pad;
  const hi = lastT + pad;
  // keep the step lines running until the right edge
  const last = rows[rows.length - 1];
  const data = last && last.t < hi ? [...rows, { ...last, t: hi }] : rows;

  const cumulative = (
    <ChartCard key="cum" title="Income and expenses over time (cumulative)" testId="fr-chart-cumulative">
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
          <CartesianGrid stroke={c.grid} vertical={false} />
          <XAxis dataKey="t" type="number" scale="time" domain={[lo, hi]} tickFormatter={dateFmt} {...ax} />
          <YAxis {...ax} tickFormatter={compact} width={56} />
          <ReferenceArea x1={evStart} x2={evEnd} fill={c.neutral} fillOpacity={0.35} ifOverflow="extendDomain"
                         label={{ value: "Event", position: "insideTop", fill: c.muted, fontSize: 12 }} />
          <Tooltip {...tt} labelFormatter={(t: any) => dateFmt(Number(t))} formatter={(v: any, n: any) => [moneyFmt(v), n]} />
          <Legend wrapperStyle={{ color: c.text, fontSize: 13 }} />
          <Line type="stepAfter" dataKey="income" name="Income" stroke={s[0]} strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line type="stepAfter" dataKey="expense" name="Expenses" stroke={s[1]} strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line type="stepAfter" dataKey="net" name="Net" stroke={c.text} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <DataTable head={["Date", "Income (cumulative)", "Expenses (cumulative)", "Net"]}
                 rows={f.cumulative.map((p: any) => [p.date, moneyFmt(p.income), moneyFmt(p.expense), moneyFmt(p.net)])} />
    </ChartCard>
  );

  const inc = Number(f.totals.income);
  const exp = Number(f.totals.expense);
  const slices = [{ label: "Income", value: inc, color: s[0] }, { label: "Expenses", value: exp, color: s[1] }].filter((x) => x.value > 0);
  const total = inc + exp;
  const donut = (
    <ChartCard key="donut" title="Income vs expenses" testId="fr-chart-donut">
      <div className="pie-wrap">
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie data={slices} dataKey="value" nameKey="label" innerRadius="52%" outerRadius="85%" paddingAngle={1}
                 stroke={c.surface} strokeWidth={2} isAnimationActive={false}>
              {slices.map((x) => <Cell key={x.label} fill={x.color} />)}
            </Pie>
            <Tooltip {...tt} formatter={(v: any, _n: any, p: any) => [moneyFmt(v), p.payload.label]} />
          </PieChart>
        </ResponsiveContainer>
        <ul className="chart-legend" aria-label="Legend">
          {slices.map((x) => (
            <li key={x.label}><span className="swatch" style={{ background: x.color }} />{x.label} <span className="muted">{total ? `${((x.value / total) * 100).toFixed(0)}%` : ""} · {moneyFmt(x.value)}</span></li>
          ))}
          <li className="legend-total">Net {moneyFmt(f.totals.net)}</li>
        </ul>
      </div>
      <DataTable head={["", "Amount"]} rows={[["Income", moneyFmt(f.totals.income)], ["Expenses", moneyFmt(f.totals.expense)]]} foot={["Net", moneyFmt(f.totals.net)]} />
    </ChartCard>
  );

  // v1.6.1 CR-034: income / expenses / net per bucket (and what is not assigned to a bucket)
  const bucketRows = [...f.buckets.items, ...(f.buckets.items.length ? [{ name: "Unassigned", ...f.buckets.unassigned }] : [])]
    .map((b: any) => ({ label: b.name, income: Number(b.income), expense: Number(b.expense), net: Number(b.net) }));
  const buckets = bucketRows.length ? (
    <ChartCard key="buckets" title="Buckets: income, expenses and net" testId="fr-chart-buckets">
      <ResponsiveContainer width="100%" height={Math.max(180, 64 * bucketRows.length + 60)}>
        <BarChart data={bucketRows} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 4 }} barGap={2}>
          <CartesianGrid stroke={c.grid} horizontal={false} />
          <XAxis type="number" {...ax} tickFormatter={compact} />
          <YAxis type="category" dataKey="label" {...ax} width={120} />
          <Tooltip {...tt} formatter={(v: any, n: any) => [moneyFmt(v), n]} />
          <Legend wrapperStyle={{ color: c.text, fontSize: 13 }} />
          <Bar dataKey="income" name="Income" fill={s[0]} radius={[0, 4, 4, 0]} maxBarSize={14} isAnimationActive={false} />
          <Bar dataKey="expense" name="Expenses" fill={s[1]} radius={[0, 4, 4, 0]} maxBarSize={14} isAnimationActive={false} />
          <Bar dataKey="net" name="Net" fill={c.other} radius={[0, 4, 4, 0]} maxBarSize={14} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <DataTable head={["Bucket", "Income", "Expenses", "Net"]} rows={bucketRows.map((b: any) => [b.label, moneyFmt(b.income), moneyFmt(b.expense), moneyFmt(b.net)])} />
    </ChartCard>
  ) : null;

  return (
    <section className="card charts" aria-labelledby="fr-charts-h">
      <h2 id="fr-charts-h">Charts</h2>
      <Masonry narrow={narrow} items={[{ key: "cum", height: 330, el: cumulative }, { key: "donut", height: 300, el: donut },
                                      ...(buckets ? [{ key: "buckets", height: 64 * bucketRows.length + 130, el: buckets }] : [])]} />
    </section>
  );
}
