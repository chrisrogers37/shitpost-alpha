import { CSSProperties } from "react";
import type { Post } from "../types/api";
import { formatTimestamp } from "../utils/time";
import { useRelativeTime } from "../hooks/useRelativeTime";
import { formatNumber } from "../utils/format";

const cardStyle: CSSProperties = {
  background: "var(--bg-card)",
  border: "1px solid var(--border)",
  borderLeft: "4px solid var(--color-blue)",
  borderRadius: "12px",
  padding: "24px",
  boxShadow: "0 1px 3px rgba(0, 0, 0, 0.06)",
};

const authorRowStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  marginBottom: "12px",
  gap: "8px",
};

const authorInfoStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "6px",
  flexWrap: "wrap",
  minWidth: 0,
};

const usernameStyle: CSSProperties = {
  fontWeight: 700,
  fontSize: "0.8rem",
  color: "var(--color-navy)",
};

const verifiedBadge: CSSProperties = {
  background: "#2563EB",
  color: "white",
  fontSize: "0.55rem",
  padding: "1px 5px",
  borderRadius: "3px",
  fontWeight: 700,
  flexShrink: 0,
};

const followersStyle: CSSProperties = {
  fontSize: "0.7rem",
  color: "var(--text-muted)",
};

const textStyle: CSSProperties = {
  fontSize: "1.05rem",
  lineHeight: 1.6,
  fontWeight: 400,
  color: "var(--text-primary)",
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
};

const engagementRow: CSSProperties = {
  display: "flex",
  gap: "16px",
  marginTop: "16px",
  fontSize: "0.75rem",
  color: "var(--text-muted)",
};

const statStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "4px",
};

const linkPreviewStyle: CSSProperties = {
  background: "var(--bg-sunken)",
  border: "1px solid var(--border-light)",
  borderRadius: "8px",
  padding: "10px 12px",
  marginTop: "12px",
  display: "flex",
  gap: "10px",
  alignItems: "center",
  textDecoration: "none",
  color: "inherit",
};

const replyContextStyle: CSSProperties = {
  borderLeft: "3px solid var(--color-blue)",
  background: "rgba(37, 99, 235, 0.04)",
  padding: "6px 12px",
  borderRadius: "0 6px 6px 0",
  marginBottom: "10px",
  fontSize: "0.8rem",
  color: "var(--text-secondary)",
};

const timestampRowStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "6px",
  marginTop: "6px",
  fontSize: "0.65rem",
  color: "var(--text-faint)",
  flexWrap: "wrap",
};

const TIMING_STYLES: Record<string, CSSProperties> = {
  PRE_MARKET: { background: "#FFF7ED", color: "#C2410C", border: "1px solid #FDBA74" },
  MARKET_OPEN: { background: "#F0FDF4", color: "#15803D", border: "1px solid #86EFAC" },
  AFTER_HOURS: { background: "#F5F3FF", color: "#7C3AED", border: "1px solid #C4B5FD" },
  CLOSED: { background: "#F8FAFC", color: "#64748B", border: "1px solid #CBD5E1" },
};

const TIMING_LABELS: Record<string, string> = {
  PRE_MARKET: "PRE-MKT",
  MARKET_OPEN: "MKT OPEN",
  AFTER_HOURS: "AFTER-HRS",
  CLOSED: "CLOSED",
};

interface Props {
  post: Post;
}

export function ShitpostCard({ post }: Props) {
  const timingKey = post.market_timing || "";
  const timingStyle = TIMING_STYLES[timingKey];
  const timingLabel = TIMING_LABELS[timingKey];
  const timeAgo = useRelativeTime(post.timestamp);

  return (
    <div style={cardStyle}>
      {/* Author row with profile + market timing badge */}
      <div style={authorRowStyle}>
        <div style={authorInfoStyle}>
          <span style={usernameStyle}>@{post.username}</span>
          {post.verified && <span style={verifiedBadge}>✓</span>}
          {post.followers_count != null && post.followers_count > 0 && (
            <span style={followersStyle}>
              {formatNumber(post.followers_count)} followers
            </span>
          )}
        </div>

        {timingStyle && timingLabel && (
          <span
            style={{
              ...timingStyle,
              fontSize: "0.6rem",
              fontWeight: 700,
              padding: "3px 8px",
              borderRadius: "4px",
              whiteSpace: "nowrap",
              letterSpacing: "0.03em",
            }}
          >
            {timingLabel}
          </span>
        )}
      </div>

      {/* Reply context */}
      {post.reply_context && (
        <div style={replyContextStyle}>
          {post.reply_context.username && (
            <span style={{ color: "var(--text-faint)", marginRight: "4px" }}>
              ↩ Replying to{" "}
              <strong style={{ color: "var(--color-navy)" }}>
                @{post.reply_context.username}
              </strong>
            </span>
          )}
          {post.reply_context.text && (
            <span>: {post.reply_context.text}</span>
          )}
        </div>
      )}

      {/* Repost indicator */}
      {post.is_repost && (
        <div
          style={{
            fontSize: "0.75rem",
            color: "var(--text-muted)",
            marginBottom: "8px",
            fontStyle: "italic",
          }}
        >
          🔁 Repost
        </div>
      )}

      {/* Post content */}
      <div style={textStyle}>{post.text}</div>

      {/* Link preview card */}
      {post.card && post.card.title && (
        <div style={linkPreviewStyle}>
          {post.card.image && (
            <img
              src={post.card.image}
              alt=""
              style={{
                width: "52px",
                height: "52px",
                borderRadius: "6px",
                objectFit: "cover",
                flexShrink: 0,
              }}
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
          )}
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: "0.75rem",
                fontWeight: 600,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                color: "var(--text-primary)",
              }}
            >
              {post.card.title}
            </div>
            {post.card.description && (
              <div
                style={{
                  fontSize: "0.7rem",
                  color: "var(--text-muted)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  marginTop: "2px",
                }}
              >
                {post.card.description}
              </div>
            )}
            {post.card.provider_name && (
              <div style={{ fontSize: "0.6rem", color: "var(--text-faint)", marginTop: "2px" }}>
                {post.card.provider_name}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Media thumbnail */}
      {post.media_attachments.length > 0 && post.media_attachments[0] && (
        <div style={{ marginTop: "12px" }}>
          {(post.media_attachments[0] as { preview_url?: string; url?: string }).preview_url && (
            <img
              src={
                (post.media_attachments[0] as { preview_url?: string }).preview_url!
              }
              alt=""
              style={{
                width: "100%",
                maxHeight: "200px",
                objectFit: "cover",
                borderRadius: "8px",
                border: "1px solid var(--border-light)",
              }}
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
          )}
        </div>
      )}

      {/* Engagement stats */}
      <div style={engagementRow}>
        <span style={statStyle}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          {formatNumber(post.engagement.replies)}
        </span>
        <span style={statStyle}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M17 1l4 4-4 4" /><path d="M3 11V9a4 4 0 0 1 4-4h14" />
            <path d="M7 23l-4-4 4-4" /><path d="M21 13v2a4 4 0 0 1-4 4H3" />
          </svg>
          {formatNumber(post.engagement.reblogs)}
        </span>
        <span style={statStyle}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
          </svg>
          {formatNumber(post.engagement.favourites)}
        </span>
      </div>

      {/* Timestamp with market timing context */}
      <div style={timestampRowStyle}>
        <time title={formatTimestamp(post.timestamp)}>
          {timeAgo}
        </time>
        {post.minutes_to_market && (
          <>
            <span>·</span>
            <span style={{ color: TIMING_STYLES[timingKey]?.color || "var(--text-faint)" }}>
              {post.minutes_to_market}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
