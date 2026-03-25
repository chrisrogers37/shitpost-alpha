import { CSSProperties } from "react";

const headerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "12px",
  padding: "24px 24px 16px",
  textAlign: "center",
};

const titleStyle: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "2rem",
  fontWeight: 700,
  letterSpacing: "0.08em",
  color: "var(--color-navy)",
  textTransform: "uppercase",
};

const subtitleStyle: CSSProperties = {
  fontFamily: "var(--font-body)",
  fontSize: "0.7rem",
  color: "var(--color-red)",
  letterSpacing: "0.06em",
  textTransform: "uppercase",
  marginTop: "2px",
  fontWeight: 600,
};

export function Header() {
  return (
    <header style={headerStyle}>
      <span style={{ fontSize: "1.6rem" }}>🦅</span>
      <div>
        <h1 style={titleStyle}>SHITPOST ALPHA</h1>
        <p style={subtitleStyle}>
          Weaponizing Shitposts for American Profit Since 2025
        </p>
      </div>
      <span style={{ fontSize: "1.6rem" }}>🇺🇸</span>
    </header>
  );
}
