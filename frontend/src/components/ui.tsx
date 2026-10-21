import type { ReactNode } from 'react';
import type { Status } from '../lib/api';
import { STATUS_LEVEL } from '../lib/format';

export function Swatch({ level, title }: { level: 0 | 1 | 2 | 3; title?: string }) {
  return <span className={`sw l${level}`} title={title} aria-hidden={!title} />;
}

export function StatusBadge({ status }: { status: Status }) {
  return <span className={`status l${STATUS_LEVEL[status]}`}>{status}</span>;
}

export function Bar({ label, value, max = 100, display, hint }: {
  label: string; value: number; max?: number; display?: string; hint?: string;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="bar" title={hint}>
      <span>{label}</span>
      <span className="track" role="meter" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={max} aria-label={label}>
        <i style={{ width: `${pct}%` }} />
      </span>
      <span className="v num">{display ?? Math.round(value)}</span>
    </div>
  );
}

export function Sparkline({ values, width = 64, height = 18, strong = false }: {
  values: (number | null)[]; width?: number; height?: number; strong?: boolean;
}) {
  const nums = values.filter((v): v is number => v !== null);
  if (nums.length < 2) return <svg width={width} height={height} aria-hidden="true" />;
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const span = max - min || 1;
  let d = '';
  let pen = false;
  values.forEach((v, i) => {
    if (v === null) {
      pen = false;
      return;
    }
    const x = (i / (values.length - 1)) * width;
    const y = height - 2 - ((v - min) / span) * (height - 4);
    d += `${pen ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`;
    pen = true;
  });
  return (
    <svg width={width} height={height} aria-hidden="true" className="spark">
      <path d={d} fill="none" stroke="#000" strokeWidth={strong ? 1.5 : 1.1} />
    </svg>
  );
}

export function Panel({ children, className = '', ...rest }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLElement>) {
  return <section className={`panel ${className}`} {...rest}>{children}</section>;
}

export function PanelHead({ title, aside }: { title: ReactNode; aside?: ReactNode }) {
  return (
    <div className="ph">
      <h3>{title}</h3>
      {aside && <span className="ph-aside">{aside}</span>}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <b>{title}</b>
      {children && <p>{children}</p>}
    </div>
  );
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-note" role="alert">
      <span>{message}</span>
      {onRetry && <button className="btn small" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function Skeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="skeleton" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => <span key={i} style={{ width: `${90 - i * 12}%` }} />)}
    </div>
  );
}

export function Diamond({ mag }: { mag: number }) {
  return <span className={`dia ${mag >= 5.5 ? 'r' : ''}`} aria-hidden="true" />;
}
