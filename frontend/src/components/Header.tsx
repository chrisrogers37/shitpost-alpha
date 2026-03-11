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
  color: "var(--color-gold)",
  textTransform: "uppercase",
};

const subtitleStyle: CSSProperties = {
  fontFamily: "var(--font-body)",
  fontSize: "0.75rem",
  color: "var(--text-muted)",
  letterSpacing: "0.05em",
  textTransform: "uppercase",
  marginTop: "4px",
};

const eagleStyle: CSSProperties = {
  width: "36px",
  height: "36px",
};

export function Header() {
  return (
    <header style={headerStyle}>
      <img src="/eagle.svg" alt="" style={eagleStyle} />
      <div>
        <h1 style={titleStyle}>SHITPOST ALPHA</h1>
        <p style={subtitleStyle}>
          Weaponizing Shitposts for American Profit Since 2025
        </p>
      </div>
      <img src="/eagle.svg" alt="" style={{ ...eagleStyle, transform: "scaleX(-1)" }} />
    </header>
  );
}
