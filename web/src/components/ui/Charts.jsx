import React from 'react';
import { useSelector } from 'react-redux';

export function SimpleBarChart({ data = [], height = 160, valueKey = 'value', labelKey = 'label' }) {
  const isDataSaver = useSelector((state) => state.ui.isDataSaverActive);

  if (!data || data.length === 0) {
    return <div className="text-xs text-slate-400 py-4 text-center">No chart data available</div>;
  }

  const maxValue = Math.max(...data.map((d) => d[valueKey] || 0), 1);

  if (isDataSaver) {
    // Accessible, low-data textual summary
    return (
      <div className="bg-slate-100 p-3 rounded-lg border border-slate-300 font-mono text-xs">
        <div className="font-bold text-slate-700 mb-2">[DATA SAVER METRICS SUMMARY]</div>
        <div className="space-y-1">
          {data.map((item, idx) => (
            <div key={idx} className="flex justify-between border-b border-slate-200 py-0.5">
              <span>{item[labelKey]}:</span>
              <span className="font-bold">{item[valueKey]}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="w-full pt-4 pb-2">
      <div className="flex items-end gap-2" style={{ height: `${height}px` }}>
        {data.map((item, idx) => {
          const val = item[valueKey] || 0;
          const heightPct = Math.round((val / maxValue) * 100);
          return (
            <div key={idx} className="flex-1 flex flex-col items-center h-full justify-end group">
              <span className="text-[10px] font-bold text-slate-600 mb-1 opacity-80 group-hover:opacity-100">
                {val}
              </span>
              <div
                className="w-full bg-emerald-500 rounded-t-sm hover:bg-emerald-600 transition-all min-h-[4px]"
                style={{ height: `${heightPct}%` }}
              />
              <span className="text-[10px] font-medium text-slate-500 truncate mt-2 w-full text-center">
                {item[labelKey]}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function MetricCard({ title, value, change, trend = 'up', subtitle, icon: Icon }) {
  const isDataSaver = useSelector((state) => state.ui.isDataSaverActive);

  return (
    <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-start justify-between">
      <div>
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{title}</p>
        <h4 className="text-2xl font-bold text-slate-900 mt-1">{value}</h4>
        {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
        {change && (
          <p className={`text-xs font-semibold mt-2 flex items-center gap-1 ${trend === 'up' ? 'text-emerald-600' : 'text-rose-600'}`}>
            <span>{trend === 'up' ? '↑' : '↓'}</span> {change}
          </p>
        )}
      </div>
      {Icon && !isDataSaver && (
        <div className="p-3 bg-emerald-50 rounded-lg text-emerald-600">
          <Icon className="h-6 w-6" />
        </div>
      )}
    </div>
  );
}
