"use client";

/* Chart measurement uses callback refs intentionally so Recharts never receives a zero-size container. */
/* eslint-disable react-hooks/refs */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Tone } from "../../lib/api";
import { toneVar, useCopy, type Copy } from "./copy";

/* --------------------------------------------------------------- motion */
const REDUCE_QUERY = "(prefers-reduced-motion: reduce)";

export function prefersReducedMotionNow() {
  return typeof window !== "undefined" && window.matchMedia(REDUCE_QUERY).matches;
}

function subscribeReducedMotion(onChange: () => void) {
  const media = window.matchMedia(REDUCE_QUERY);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

/** Read synchronously on the client, so the first chart render already knows the preference. */
export function useReducedMotion() {
  return useSyncExternalStore(subscribeReducedMotion, prefersReducedMotionNow, () => false);
}

/**
 * Count-up on first render, then animate old → new on every change and flag `changed` briefly so
 * the card can highlight where an action landed. Under reduced motion the final value shows at once.
 */
export function useAnimatedValue(value: number) {
  const [display, setDisplay] = useState(() => (prefersReducedMotionNow() ? value : 0));
  const [changed, setChanged] = useState(false);
  const shown = useRef(display);
  const target = useRef<number | null>(null);

  useEffect(() => {
    const isUpdate = target.current !== null && target.current !== value;
    target.current = value;
    const from = shown.current;
    let frame = 0;
    let timer: number | undefined;
    if (isUpdate) {
      setChanged(true);
      timer = window.setTimeout(() => setChanged(false), 1600);
    }
    if (prefersReducedMotionNow() || from === value) {
      shown.current = value;
      setDisplay(value);
    } else {
      const start = performance.now();
      const duration = isUpdate ? 700 : 900;
      const tick = (now: number) => {
        const progress = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - progress, 3);
        const next = Math.round(from + (value - from) * eased);
        shown.current = next;
        setDisplay(next);
        if (progress < 1) frame = window.requestAnimationFrame(tick);
      };
      frame = window.requestAnimationFrame(tick);
    }
    return () => {
      window.cancelAnimationFrame(frame);
      if (timer) window.clearTimeout(timer);
    };
  }, [value]);

  return { display, changed };
}

/** Inline animated integer; always renders a number, never an empty string. */
export function AnimatedNumber({ value }: { value: number }) {
  const { display } = useAnimatedValue(value);
  return <span className="signoff-num">{display}</span>;
}

export function useChartSize() {
  const [node, setNode] = useState<HTMLElement | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const setElement = useCallback((element: HTMLElement | null) => setNode(element), []);

  useEffect(() => {
    if (!node) return;
    const measure = () => {
      const rect = node.getBoundingClientRect();
      const next = {
        width: Math.max(0, Math.round(rect.width)),
        height: Math.max(0, Math.round(rect.height)),
      };
      setSize((current) =>
        current.width === next.width && current.height === next.height ? current : next,
      );
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [node]);

  return { setElement, ...size };
}

/* ------------------------------------------------------- KPI mini charts */
export function Sparkline({ values }: { values: number[] }) {
  const chart = useChartSize();
  const reduced = useReducedMotion();
  return (
    <div className="reference-coverage-chart" aria-hidden="true">
      <div ref={chart.setElement} className="reference-chart-frame">
        {chart.width > 0 && chart.height > 0 && values.length > 1 && (
          <AreaChart
            width={chart.width}
            height={chart.height}
            data={values.map((value, index) => ({ index, value }))}
            margin={{ top: 2, right: 0, bottom: 0, left: 0 }}
          >
            <defs>
              <linearGradient id="signoffSparkFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--reference-lime)" stopOpacity={0.45} />
                <stop offset="100%" stopColor="var(--reference-lime)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <YAxis hide domain={["dataMin - 4", "dataMax + 2"]} />
            <Area
              type="monotone"
              dataKey="value"
              stroke="var(--reference-primary)"
              strokeWidth={2}
              fill="url(#signoffSparkFill)"
              dot={false}
              isAnimationActive={!reduced}
              animationDuration={520}
              animationEasing="ease-out"
            />
          </AreaChart>
        )}
      </div>
    </div>
  );
}

export function MiniRing({ value }: { value: number }) {
  const chart = useChartSize();
  const reduced = useReducedMotion();
  const data = [
    { name: "done", value, fill: "var(--reference-success)" },
    { name: "rest", value: Math.max(0, 100 - value), fill: "var(--reference-border)" },
  ];
  return (
    <div ref={chart.setElement} className="reference-mini-ring" aria-hidden="true">
      {chart.width > 0 && chart.height > 0 && (
        <PieChart width={chart.width} height={chart.height}>
          <Pie
            data={data}
            dataKey="value"
            innerRadius="70%"
            outerRadius="100%"
            startAngle={90}
            endAngle={-270}
            cornerRadius={2}
            stroke="none"
            isAnimationActive={!reduced}
            animationDuration={520}
            animationEasing="ease-out"
          >
            {data.map((entry) => (
              <Cell key={entry.name} fill={entry.fill} />
            ))}
          </Pie>
        </PieChart>
      )}
    </div>
  );
}

/** 100% stacked bar under a KPI number; the numbers are the legend. */
export function StackedBar({
  items,
}: {
  items: { key: string; label: string; value: number; tone: Tone }[];
}) {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  return (
    <div className="signoff-stack">
      <div
        className="signoff-stack-bar"
        role="img"
        aria-label={items.map((item) => `${item.value} ${item.label}`).join(", ")}
      >
        {items
          .filter((item) => item.value > 0)
          .map((item) => (
            <span
              key={item.key}
              style={{
                flexBasis: `${total ? (item.value / total) * 100 : 0}%`,
                background: toneVar[item.tone],
              }}
            />
          ))}
      </div>
      <div className="reference-metric-items">
        {items.map((item) => (
          <span key={item.key}>
            <i className="status-dot" style={{ background: toneVar[item.tone] }} />
            <b>
              <AnimatedNumber value={item.value} />
            </b>{" "}
            {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}

/* --------------------------------------------- verification status bars */
export function VerificationBars({
  items,
}: {
  items: { key: string; label: string; value: number; tone: Tone }[];
}) {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  const sorted = items.slice().sort((a, b) => b.value - a.value);
  const max = Math.max(1, ...sorted.map((item) => item.value));
  return (
    <div className="signoff-hbars">
      {sorted.map((item) => {
        const percent = total ? Math.round((item.value / total) * 100) : 0;
        return (
          <div className="signoff-hbar" key={item.key}>
            <span className="signoff-hbar-label">{item.label}</span>
            <span className="signoff-hbar-track">
              <span
                className="signoff-hbar-fill"
                style={{ width: `${(item.value / max) * 100}%`, background: toneVar[item.tone] }}
              />
            </span>
            <span className="signoff-hbar-value">
              <b>
                <AnimatedNumber value={item.value} />
              </b>
              <small>{percent}%</small>
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* -------------------------------------------------- coverage trend card */
type TrendPoint = { run: number; value: number; at: string; delta: number | null };

export function CoverageTrendChart({ trend }: { trend: { run: number; value: number; at: string }[] }) {
  const { c, locale } = useCopy();
  const chart = useChartSize();
  const reduced = useReducedMotion();
  const data: TrendPoint[] = trend.map((point, index) => ({
    ...point,
    delta: index === 0 ? null : point.value - trend[index - 1].value,
  }));
  const last = data[data.length - 1];
  const min = data.length ? Math.min(...data.map((point) => point.value)) : 0;
  // Even ticks up to 100: steps of 10 for a tight range, 20 otherwise (floor snapped to the step).
  const rawFloor = Math.max(0, Math.floor(min / 10) * 10);
  const step = 100 - rawFloor <= 50 ? 10 : 20;
  const floor = Math.max(0, 100 - Math.ceil((100 - rawFloor) / step) * step);
  const ticks = Array.from({ length: (100 - floor) / step + 1 }, (_, index) => floor + index * step);

  return (
    <div className="signoff-trend">
      <div className="signoff-trend-summary">
        <strong>{last ? `${last.value}%` : "—"}</strong>
      </div>
      <div ref={chart.setElement} className="signoff-trend-frame">
        {chart.width > 0 && chart.height > 0 && data.length > 0 && (
          <LineChart
            width={chart.width}
            height={chart.height}
            data={data}
            margin={{ top: 26, right: 18, bottom: 4, left: -8 }}
            accessibilityLayer
          >
            <CartesianGrid stroke="var(--reference-border)" strokeDasharray="3 4" vertical={false} />
            <XAxis
              dataKey="run"
              tickFormatter={(run: number) => c.run(run)}
              tick={{ fill: "var(--reference-subtle)", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "var(--reference-border)" }}
              interval="preserveStartEnd"
              minTickGap={18}
            />
            <YAxis
              domain={[floor, 100]}
              ticks={ticks}
              interval={0}
              tickFormatter={(value: number) => `${value}%`}
              tick={{ fill: "var(--reference-subtle)", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={44}
            />
            <Tooltip
              cursor={{ stroke: "var(--reference-border-strong)" }}
              content={({ active, payload }) => {
                const point = active && payload?.[0] ? (payload[0].payload as TrendPoint) : null;
                if (!point) return null;
                return <TrendTooltip point={point} c={c} locale={locale} />;
              }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="var(--reference-primary)"
              strokeWidth={2}
              isAnimationActive={!reduced}
              animationDuration={650}
              animationEasing="ease-out"
              activeDot={{ r: 5, fill: "var(--reference-primary)", stroke: "var(--reference-surface)", strokeWidth: 2 }}
              dot={(props: { cx?: number; cy?: number; index?: number }) => {
                const { cx = 0, cy = 0, index = 0 } = props;
                if (index !== data.length - 1) {
                  return <circle key={`dot-${index}`} cx={cx} cy={cy} r={2.5} fill="var(--reference-primary)" />;
                }
                return (
                  <g key={`dot-${index}`}>
                    <circle cx={cx} cy={cy} r={5} fill="var(--reference-primary)" stroke="var(--reference-surface)" strokeWidth={2} />
                    {last?.delta !== null && last?.delta !== undefined && (
                      <text
                        x={cx}
                        y={cy - 12}
                        textAnchor="end"
                        className="signoff-trend-label"
                        fill="var(--reference-text)"
                        fontSize={11}
                        fontWeight={600}
                      >
                        {c.ptsVsPrevious(last.delta)}
                      </text>
                    )}
                  </g>
                );
              }}
            />
          </LineChart>
        )}
      </div>
    </div>
  );
}

function TrendTooltip({ point, c, locale }: { point: TrendPoint; c: Copy; locale: string }) {
  const date = point.at
    ? new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" }).format(new Date(point.at))
    : "";
  return (
    <div className="signoff-chart-tooltip">
      <span>
        {c.run(point.run)}
        {date ? ` · ${date}` : ""}
      </span>
      <strong>{point.value}%</strong>
      <small>{point.delta === null ? c.firstRun : c.ptsVsPrevious(point.delta)}</small>
    </div>
  );
}
