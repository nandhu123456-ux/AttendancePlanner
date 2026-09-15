import { useEffect, useState } from "react";
import { getUserInfo, getUserPhoto } from "../api/api";
import "./StudentProfile.css";

// Photo object-URL cache, keyed by student_id. Navigating between Dashboard
// and Settings (or re-rendering after a prediction refresh) reuses the same
// URL instead of downloading the image again.
const photoCache = new Map();

const initialsFrom = (name, fallbackId) => {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length) {
    return parts.slice(0, 2).map((part) => part[0].toUpperCase()).join("");
  }
  const id = (fallbackId || "").trim();
  return id ? id.slice(0, 2).toUpperCase() : "ST";
};

export default function StudentProfile({ studentId, showEmail = false }) {
  const [profile, setProfile] = useState(null);
  const [photoUrl, setPhotoUrl] = useState(() => photoCache.get(studentId) || null);

  useEffect(() => {
    if (!studentId) return undefined;
    let cancelled = false;

    getUserInfo(studentId)
      .then(({ data }) => {
        if (cancelled) return;
        setProfile(data);
        if (data.photo_url && !photoCache.has(studentId)) {
          // Photo is proxied through the backend (never GITAM cookies in the
          // browser). It is fetched once per session and cached.
          getUserPhoto(studentId)
            .then((res) => {
              if (cancelled) return;
              const url = URL.createObjectURL(res.data);
              photoCache.set(studentId, url);
              setPhotoUrl(url);
            })
            .catch(() => {
              // Photo unavailable — the initials avatar is shown instead.
            });
        }
      })
      .catch(() => {
        // Profile not synced yet (e.g. accounts created before this feature).
        // Never block the page — the component simply stays hidden.
      });

    return () => {
      cancelled = true;
    };
  }, [studentId]);

  if (!profile) return null;

  return (
    <section className="student-profile" aria-label="Student profile">
      {photoUrl ? (
        <img className="student-profile-photo" src={photoUrl} alt={profile.full_name || "Profile photo"} />
      ) : (
        <span className="student-profile-avatar" aria-hidden="true">
          {initialsFrom(profile.full_name, profile.student_id || studentId)}
        </span>
      )}
      <span className="student-profile-meta">
        <strong className="student-profile-name">{profile.full_name || "Student"}</strong>
        <span className="student-profile-id">{profile.student_id || studentId}</span>
        {showEmail && profile.email && <span className="student-profile-email">{profile.email}</span>}
      </span>
    </section>
  );
}
