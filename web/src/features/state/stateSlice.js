import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { api } from '../../api/client';

export const fetchStateSchools = createAsyncThunk('state/fetchSchools', async (_, { rejectWithValue }) => {
  try {
    return await api.getStateSchools();
  } catch (err) {
    return rejectWithValue(err.message);
  }
});

export const fetchComplianceMap = createAsyncThunk('state/fetchComplianceMap', async (_, { rejectWithValue }) => {
  try {
    return await api.getComplianceMap();
  } catch (err) {
    return rejectWithValue(err.message);
  }
});

export const fetchStateAlarms = createAsyncThunk('state/fetchAlarms', async (_, { rejectWithValue }) => {
  try {
    return await api.getStateAlarms();
  } catch (err) {
    return rejectWithValue(err.message);
  }
});

export const fetchStateSummary = createAsyncThunk('state/fetchSummary', async (_, { rejectWithValue }) => {
  try {
    return await api.getStateSummary();
  } catch (err) {
    return rejectWithValue(err.message);
  }
});

const stateSlice = createSlice({
  name: 'state',
  initialState: {
    schools: [],
    complianceMap: [],
    alarms: [],
    summary: null,
    loading: false,
    error: null,
  },
  reducers: {
    addLiveAlarm: (state, action) => {
      state.alarms.unshift(action.payload);
      // update compliance map entry
      const mapItem = state.complianceMap.find((item) => item.school_id === action.payload.school_id);
      if (mapItem) {
        mapItem.alarm = true;
      }
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchStateSchools.fulfilled, (state, action) => {
        state.schools = action.payload;
      })
      .addCase(fetchComplianceMap.fulfilled, (state, action) => {
        state.complianceMap = action.payload;
      })
      .addCase(fetchStateAlarms.fulfilled, (state, action) => {
        state.alarms = action.payload;
      })
      .addCase(fetchStateSummary.fulfilled, (state, action) => {
        state.summary = action.payload;
      });
  },
});

export const { addLiveAlarm } = stateSlice.actions;
export default stateSlice.reducer;
