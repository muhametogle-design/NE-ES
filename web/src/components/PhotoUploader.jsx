import React, { useRef, useState } from 'react';
import { api } from '../api/client';
import { Button } from './ui/Button';
import { Camera, Loader2 } from 'lucide-react';

const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_SIZE = 5 * 1024 * 1024; // Mirrors the backend's 5 MB cap.

/**
 * Reusable student/teacher photo field.
 *
 * Uploads immediately on file select via POST /api/v1/media/upload and lifts
 * the stored photo_url to the parent form through onChange. Removing clears
 * the value (parent sends explicit null, which the API treats as "clear").
 */
export function PhotoUploader({ value, onChange, label = 'Photo', disabled = false }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  const handleSelect = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;

    // Client-side pre-checks mirror the backend rules so users get instant
    // feedback; the server still enforces type/size independently.
    if (!ALLOWED_TYPES.includes(file.type)) {
      setError('Only JPEG, PNG, and WebP photos are allowed');
      return;
    }
    if (!file.size || file.size > MAX_SIZE) {
      setError('Photo must be non-empty and not exceed 5 MB');
      return;
    }

    try {
      setUploading(true);
      setError(null);
      const result = await api.uploadPhoto(file);
      onChange(result.photo_url);
    } catch (err) {
      setError(err.message || 'Photo upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <span className="block text-xs font-semibold text-slate-600 mb-1.5">{label}</span>
      <div className="flex items-center gap-3">
        <div className="h-16 w-16 rounded-full overflow-hidden bg-slate-100 border border-slate-200 flex items-center justify-center shrink-0">
          {value ? (
            <img src={value} alt="Profile photo preview" className="h-full w-full object-cover" />
          ) : (
            <Camera className="h-6 w-6 text-slate-300" />
          )}
        </div>
        <div className="flex flex-col gap-1.5">
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={disabled || uploading}
              onClick={() => inputRef.current?.click()}
              className="flex items-center gap-1.5"
            >
              {uploading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {uploading ? 'Uploading…' : value ? 'Replace' : 'Upload'}
            </Button>
            {value && !uploading && (
              <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={() => onChange(null)}>
                Remove
              </Button>
            )}
          </div>
          <p className="text-[11px] text-slate-400">JPEG, PNG or WebP, max 5 MB</p>
        </div>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={handleSelect}
        disabled={disabled || uploading}
      />
      {error && <p className="mt-1.5 text-xs text-rose-600">{error}</p>}
    </div>
  );
}
