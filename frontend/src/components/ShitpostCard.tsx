import { CSSProperties } from "react";
import type { Post } from "../types/api";
import { relativeTime, formatTimestamp } from "../utils/time";
import { formatNumber } from "../utils/format";

const cardStyle: CSSProperties = {
  background: "var(--bg-card)",
  border: "1px solid var(--border)",
  borderLeft: "4px solid var(--color-blue)",
  borderRadius: "12px",
  padding: "24px",
  boxShadow: "0 1px 3px rgba(0, 0, 0, 0.06)",
};

const metaStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  marginBottom: "12px",
  fontSize: "0.8rem",
  color: "var(--text-muted)",
};

const usernameStyle: CSSProperties = {
  fontWeight: 700,
  color: "var(--color-navy)",
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

interface Props {
  post: Post;
}

export function ShitpostCard({ post }: Props) {
  return (
    <div style={cardStyle}>
      <div style={metaStyle}>
        <span>
          <span style={usernameStyle}>@{post.username}</span>
          {" "}on Truth Social
        </span>
        <time title={formatTimestamp(post.timestamp)}>
          {relativeTime(post.timestamp)}
        </time>
      </div>

      <div style={textStyle}>{post.text}</div>

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
    </div>
  );
}
