import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { api } from '../../api/client';

export const fetchStudents = createAsyncThunk('school/fetchStudents', async (params, { rejectWithValue }) => {
  try {
    return await api.getStudents(params);
  } catch (err) {
    return rejectWithValue(err.message);
  }
});

export const fetchClasses = createAsyncThunk('school/fetchClasses', async (_, { rejectWithValue }) => {
  try {
    return await api.getClasses();
  } catch (err) {
    return rejectWithValue(err.message);
  }
});

export const fetchSubjects = createAsyncThunk('school/fetchSubjects', async (level, { rejectWithValue }) => {
  try {
    return await api.getSubjects(level);
  } catch (err) {
    return rejectWithValue(err.message);
  }
});

export const fetchTeachers = createAsyncThunk('school/fetchTeachers', async (_, { rejectWithValue }) => {
  try {
    return await api.getTeachers();
  } catch (err) {
    return rejectWithValue(err.message);
  }
});

export const fetchFinanceSummary = createAsyncThunk('school/fetchFinanceSummary', async (_, { rejectWithValue }) => {
  try {
    return await api.getFinanceSummary();
  } catch (err) {
    return rejectWithValue(err.message);
  }
});

const schoolSlice = createSlice({
  name: 'school',
  initialState: {
    students: { items: [], total: 0, page: 1, pages: 1 },
    classes: [],
    subjects: [],
    teachers: [],
    financeSummary: null,
    loading: false,
    error: null,
  },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchStudents.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchStudents.fulfilled, (state, action) => {
        state.loading = false;
        state.students = action.payload;
      })
      .addCase(fetchStudents.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      .addCase(fetchClasses.fulfilled, (state, action) => {
        state.classes = action.payload;
      })
      .addCase(fetchSubjects.fulfilled, (state, action) => {
        state.subjects = action.payload;
      })
      .addCase(fetchTeachers.fulfilled, (state, action) => {
        state.teachers = action.payload;
      })
      .addCase(fetchFinanceSummary.fulfilled, (state, action) => {
        state.financeSummary = action.payload;
      });
  },
});

export default schoolSlice.reducer;
