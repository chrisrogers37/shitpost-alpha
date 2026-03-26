import { CSSProperties } from "react";

const footerStyle: CSSProperties = {
  textAlign: "center",
  padding: "24px 16px 32px",
  fontSize: "0.7rem",
  color: "var(--text-faint)",
  maxWidth: "600px",
  margin: "0 auto",
  lineHeight: 1.6,
};

export function Footer() {
  return (
    <footer style={footerStyle}>
      <div className="patriotic-divider" style={{ marginBottom: "16px" }} />
      <p>
        NOT FINANCIAL ADVICE. This is a shitpost analysis tool built for
        entertainment and educational purposes. Any resemblance to actual
        investment strategy is purely coincidental and deeply concerning. Past
        performance of shitposts does not guarantee future results. Please
        consult a licensed financial advisor before making any investment
        decisions. God bless America.
      </p>
    </footer>
  );
}
