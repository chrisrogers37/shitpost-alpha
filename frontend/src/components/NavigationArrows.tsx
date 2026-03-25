import { CSSProperties } from "react";

const arrowBase: CSSProperties = {
  position: "fixed",
  top: "50%",
  transform: "translateY(-50%)",
  zIndex: 10,
  background: "rgba(59, 130, 246, 0.15)",
  border: "1px solid rgba(59, 130, 246, 0.4)",
  borderRadius: "50%",
  width: "44px",
  height: "44px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  cursor: "pointer",
  color: "var(--text-primary)",
  fontSize: "1.2rem",
  transition: "all 0.15s ease",
};

const disabledStyle: CSSProperties = {
  opacity: 0.2,
  cursor: "default",
  pointerEvents: "none",
};

interface Props {
  hasNewer: boolean;
  hasOlder: boolean;
  onNewer: () => void;
  onOlder: () => void;
}

export function NavigationArrows({ hasNewer, hasOlder, onNewer, onOlder }: Props) {
  return (
    <>
      <button
        style={{
          ...arrowBase,
          left: "12px",
          ...(hasNewer ? {} : disabledStyle),
        }}
        onClick={onNewer}
        disabled={!hasNewer}
        title="Newer dispatch (Left arrow)"
        aria-label="Navigate to newer post"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </button>
      <button
        style={{
          ...arrowBase,
          right: "12px",
          ...(hasOlder ? {} : disabledStyle),
        }}
        onClick={onOlder}
        disabled={!hasOlder}
        title="Older dispatch (Right arrow)"
        aria-label="Navigate to older post"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="9 18 15 12 9 6" />
        </svg>
      </button>
    </>
  );
}
