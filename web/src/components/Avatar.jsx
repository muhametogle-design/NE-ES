import React, { useState } from 'react';

/**
 * Profile photo with an initials fallback.
 *
 * A broken/missing photo_url degrades gracefully to initials instead of a
 * broken-image icon. Failure is tracked per-URL so a newly uploaded photo
 * renders even if a previous URL for the same record failed to load.
 */
export function Avatar({
  photoUrl,
  firstName = '',
  lastName = '',
  className = 'h-8 w-8 text-xs',
  fallbackClassName = 'bg-slate-200 text-slate-700',
}) {
  const [failedUrl, setFailedUrl] = useState(null);
  const initials = `${firstName?.[0] || ''}${lastName?.[0] || ''}`.toUpperCase() || '?';

  if (photoUrl && failedUrl !== photoUrl) {
    return (
      <img
        src={photoUrl}
        alt={`${firstName} ${lastName}`.trim() || 'Profile photo'}
        onError={() => setFailedUrl(photoUrl)}
        className={`${className} rounded-full object-cover shrink-0 bg-slate-100`}
      />
    );
  }

  return (
    <div
      className={`${className} ${fallbackClassName} rounded-full flex items-center justify-center font-bold shrink-0`}
      aria-hidden={!photoUrl}
    >
      {initials}
    </div>
  );
}
