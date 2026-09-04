import React, { useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { setDataSaverMode } from '../../features/ui/uiSlice';
import { Zap, Wifi } from 'lucide-react';

export function DataSaverToggle() {
  const dispatch = useDispatch();
  const { dataSaverMode, isDataSaverActive } = useSelector((state) => state.ui);

  useEffect(() => {
    // Initial sync
    dispatch(setDataSaverMode(dataSaverMode));

    // Listen to network changes if supported
    if (typeof navigator !== 'undefined' && navigator.connection) {
      const handleConnectionChange = () => {
        if (dataSaverMode === 'auto') {
          dispatch(setDataSaverMode('auto'));
        }
      };
      navigator.connection.addEventListener('change', handleConnectionChange);
      return () => navigator.connection.removeEventListener('change', handleConnectionChange);
    }
  }, [dispatch, dataSaverMode]);

  return (
    <div className="flex items-center gap-2 bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200 text-xs">
      <div className="flex items-center gap-1 font-semibold text-slate-700">
        <Zap className={`h-3.5 w-3.5 ${isDataSaverActive ? 'text-amber-500 fill-amber-500' : 'text-slate-400'}`} />
        <span>Data Saver:</span>
      </div>
      <div className="flex bg-white rounded border border-slate-200 overflow-hidden p-0.5">
        {['off', 'auto', 'on'].map((mode) => (
          <button
            key={mode}
            type="button"
            onClick={() => dispatch(setDataSaverMode(mode))}
            className={`px-2 py-0.5 text-[10px] font-bold uppercase rounded-sm transition-colors ${
              dataSaverMode === mode
                ? 'bg-slate-800 text-white shadow-xs'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            {mode}
          </button>
        ))}
      </div>
      {isDataSaverActive && (
        <span className="bg-amber-100 text-amber-800 text-[9px] font-extrabold uppercase px-1.5 py-0.5 rounded">
          Active
        </span>
      )}
    </div>
  );
}
