import { CSSProperties } from "react";

const headerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "12px",
  padding: "20px 24px 16px",
  textAlign: "center",
};

const titleStyle: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "2rem",
  fontWeight: 700,
  letterSpacing: "0.08em",
  background: "linear-gradient(135deg, #EF4444 0%, #FFFFFF 50%, #3B82F6 100%)",
  WebkitBackgroundClip: "text",
  WebkitTextFillColor: "transparent",
  textTransform: "uppercase",
};

const subtitleStyle: CSSProperties = {
  fontFamily: "var(--font-body)",
  fontSize: "0.75rem",
  color: "#3B82F6",
  letterSpacing: "0.05em",
  textTransform: "uppercase",
  marginTop: "4px",
  fontWeight: 500,
};

export function Header() {
  return (
    <header style={headerStyle}>
      <span style={{ fontSize: "1.8rem" }}>🦅</span>
      <div>
        <h1 style={titleStyle}>SHITPOST ALPHA</h1>
        <p style={subtitleStyle}>
          Weaponizing Shitposts for American Profit Since 2025
        </p>
      </div>
      <span style={{ fontSize: "1.8rem" }}>🇺🇸</span>
    </header>
  );
}
