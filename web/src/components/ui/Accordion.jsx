import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';

export function Accordion({ items = [] }) {
  const [openIndex, setOpenIndex] = useState(0);

  return (
    <div className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white overflow-hidden">
      {items.map((item, idx) => {
        const isOpen = openIndex === idx;
        return (
          <div key={idx} className="transition-colors">
            <button
              type="button"
              onClick={() => setOpenIndex(isOpen ? -1 : idx)}
              className="flex w-full items-center justify-between px-4 py-3.5 text-left text-sm font-semibold text-slate-800 hover:bg-slate-50"
            >
              <span>{item.title}</span>
              <ChevronDown className={`h-4 w-4 text-slate-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>
            {isOpen && <div className="px-4 pb-4 pt-1 text-sm text-slate-600">{item.content}</div>}
          </div>
        );
      })}
    </div>
  );
}
