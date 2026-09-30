import React from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ForecastResponse } from '../api/client';

interface ForecastPanelProps {
  forecast: ForecastResponse | null;
}

const ForecastPanel: React.FC<ForecastPanelProps> = ({ forecast }) => {
  const data = forecast
    ? [
        ...forecast.history.map((h) => ({ time: h.time, actual: h.value, forecast: null as number | null })),
        ...forecast.points.map((p, i) => ({
          time: p.time,
          actual: i === 0 ? forecast.history[forecast.history.length - 1]?.value ?? null : null,
          forecast: p.value,
        })),
      ]
    : [];

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-900/80 p-4 backdrop-blur">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="text-[11px] font-bold uppercase tracking-widest text-slate-400">
          6-Hour Flight Forecast
        </h2>
        {forecast && (
          <span className="text-[10px] text-slate-500">{forecast.region_name}</span>
        )}
      </div>
      {forecast ? (
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 5, right: 8, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="time" stroke="#64748b" fontSize={10} tickLine={false} />
              <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: '#94a3b8' }}
              />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Line type="monotone" dataKey="actual" stroke="#38bdf8" strokeWidth={2} dot={false} name="Observed" connectNulls />
              <Line type="monotone" dataKey="forecast" stroke="#fbbf24" strokeWidth={2} strokeDasharray="5 4" dot={false} name="Forecast" connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="text-sm text-slate-500">Select a region to see its forecast.</p>
      )}
    </div>
  );
};

export default ForecastPanel;
