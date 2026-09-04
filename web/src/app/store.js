import { configureStore } from '@reduxjs/toolkit';
import authReducer from '../features/auth/authSlice';
import schoolReducer from '../features/school/schoolSlice';
import stateReducer from '../features/state/stateSlice';
import uiReducer from '../features/ui/uiSlice';

export const store = configureStore({
  reducer: {
    auth: authReducer,
    school: schoolReducer,
    state: stateReducer,
    ui: uiReducer,
  },
});
