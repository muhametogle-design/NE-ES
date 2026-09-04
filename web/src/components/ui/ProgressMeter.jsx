import React from 'react';

export function ProgressMeter({
  value = 0,
  max = 100,
  label,
  showPercentage = true,
  color = 'emerald', // 'emerald' | 'blue' | 'amber' | 'rose'
  className = '',
}) {
  const percentage = Math.min(100, Math.max(0, Math.round((value / max) * 100)));

  const colorMap = {
    emerald: 'bg-emerald-500',
    blue: 'bg-blue-500',
    amber: 'bg-amber-500',
    rose: 'bg-rose-500',
  };

  return (
    <div className={`w-full ${className}`}>
      {(label || showPercentage) && (
        <div className="flex justify-between items-center mb-1 text-xs font-semibold text-slate-700">
          {label && <span>{label}</span>}
          {showPercentage && <span>{percentage}%</span>}
        </div>
      )}
      <div className="w-full bg-slate-200 rounded-full h-2.5 overflow-hidden">
        <div
          className={`h-2.5 rounded-full transition-all duration-300 ${colorMap[color] || colorMap.emerald}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
