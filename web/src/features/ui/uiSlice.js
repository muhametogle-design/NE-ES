import { createSlice } from '@reduxjs/toolkit';

const getInitialDataSaver = () => {
  const saved = localStorage.getItem('data_saver_mode');
  if (saved) return saved;
  if (typeof navigator !== 'undefined' && navigator.connection && navigator.connection.saveData) {
    return 'on';
  }
  return 'auto';
};

const uiSlice = createSlice({
  name: 'ui',
  initialState: {
    sidebarOpen: true,
    dataSaverMode: getInitialDataSaver(), // 'off' | 'auto' | 'on'
    isDataSaverActive: false,
    toasts: [],
  },
  reducers: {
    toggleSidebar: (state) => {
      state.sidebarOpen = !state.sidebarOpen;
    },
    setSidebarOpen: (state, action) => {
      state.sidebarOpen = action.payload;
    },
    setDataSaverMode: (state, action) => {
      state.dataSaverMode = action.payload;
      localStorage.setItem('data_saver_mode', action.payload);
      if (action.payload === 'on') {
        state.isDataSaverActive = true;
      } else if (action.payload === 'off') {
        state.isDataSaverActive = false;
      } else {
        // Auto: check navigator.connection
        state.isDataSaverActive = !!(typeof navigator !== 'undefined' && navigator.connection && navigator.connection.saveData);
      }
      if (typeof document !== 'undefined') {
        if (state.isDataSaverActive) {
          document.documentElement.classList.add('data-saver-active');
        } else {
          document.documentElement.classList.remove('data-saver-active');
        }
      }
    },
    addToast: (state, action) => {
      state.toasts.push({
        id: Date.now(),
        type: action.payload.type || 'info', // 'success' | 'error' | 'warning' | 'info'
        message: action.payload.message,
      });
    },
    removeToast: (state, action) => {
      state.toasts = state.toasts.filter((t) => t.id !== action.payload);
    },
  },
});

export const { toggleSidebar, setSidebarOpen, setDataSaverMode, addToast, removeToast } = uiSlice.actions;
export default uiSlice.reducer;
