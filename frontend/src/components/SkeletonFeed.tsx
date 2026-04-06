import { CSSProperties } from "react";

const shimmer = `
@keyframes shimmer {
  0% { background-position: -400px 0; }
  100% { background-position: 400px 0; }
}
`;

const skeletonBar = (
  width: string,
  height: string = "14px",
  marginBottom: string = "8px",
): CSSProperties => ({
  width,
  height,
  borderRadius: "4px",
  background: "linear-gradient(90deg, var(--bg-sunken) 25%, var(--border-light) 50%, var(--bg-sunken) 75%)",
  backgroundSize: "800px 100%",
  animation: "shimmer 1.5s infinite linear",
  marginBottom,
});

const cardStyle: CSSProperties = {
  background: "var(--bg-card)",
  border: "1px solid var(--border-light)",
  borderRadius: "12px",
  padding: "20px",
  marginTop: "12px",
};

export function SkeletonFeed() {
  return (
    <div style={{ maxWidth: "640px", margin: "0 auto", padding: "0 16px 24px" }}>
      <style>{shimmer}</style>

      {/* Post card skeleton */}
      <div style={{ ...cardStyle, borderLeft: "4px solid var(--border)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "16px" }}>
          <div style={skeletonBar("180px", "16px")} />
          <div style={skeletonBar("60px", "22px", "0")} />
        </div>
        <div style={skeletonBar("100%", "16px")} />
        <div style={skeletonBar("90%", "16px")} />
        <div style={skeletonBar("70%", "16px")} />
        <div style={{ display: "flex", gap: "16px", marginTop: "16px" }}>
          <div style={skeletonBar("50px", "12px", "0")} />
          <div style={skeletonBar("50px", "12px", "0")} />
          <div style={skeletonBar("50px", "12px", "0")} />
        </div>
      </div>

      {/* Prediction panel skeleton */}
      <div style={{ ...cardStyle, borderLeft: "4px solid var(--border)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "12px" }}>
          <div style={skeletonBar("140px", "14px", "0")} />
          <div style={skeletonBar("80px", "18px", "0")} />
        </div>
        <div style={{ ...cardStyle, background: "var(--bg-sunken)", marginTop: "8px", padding: "14px" }}>
          <div style={skeletonBar("100%", "14px")} />
          <div style={skeletonBar("85%", "14px")} />
          <div style={skeletonBar("60%", "14px", "0")} />
        </div>
      </div>

      {/* Ticker pills skeleton */}
      <div style={{ display: "flex", gap: "8px", justifyContent: "center", marginTop: "12px" }}>
        <div style={skeletonBar("64px", "32px", "0")} />
        <div style={skeletonBar("64px", "32px", "0")} />
        <div style={skeletonBar("64px", "32px", "0")} />
      </div>

      {/* Price KPI skeleton */}
      <div style={{ ...cardStyle, display: "flex", justifyContent: "space-between" }}>
        <div>
          <div style={skeletonBar("80px", "10px")} />
          <div style={skeletonBar("100px", "24px", "0")} />
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={skeletonBar("80px", "10px")} />
          <div style={skeletonBar("100px", "24px", "0")} />
        </div>
      </div>

      {/* Chart skeleton */}
      <div style={{ ...cardStyle, height: "300px" }}>
        <div style={skeletonBar("100%", "100%", "0")} />
      </div>
    </div>
  );
}
