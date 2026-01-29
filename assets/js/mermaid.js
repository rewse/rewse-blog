function css(name) {
  return "rgb(" + getComputedStyle(document.documentElement).getPropertyValue(name) + ")";
}

// Get RGB values from CSS variable and return as array [r, g, b]
function getRgb(name) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value.split(",").map(v => parseInt(v.trim(), 10));
}

// Reduce saturation by mixing color with gray (50% each)
function desaturate(colorName, grayName) {
  const color = getRgb(colorName);
  const gray = getRgb(grayName);
  const mixed = color.map((c, i) => Math.round((c + gray[i]) / 2));
  return "rgb(" + mixed.join(", ") + ")";
}

function initMermaidLight() {
  mermaid.initialize({
    theme: "base",
    themeVariables: {
      background: css("--color-neutral"),
      primaryColor: desaturate("--color-primary-200", "--color-neutral-200"),
      secondaryColor: desaturate("--color-secondary-200", "--color-neutral-200"),
      tertiaryColor: css("--color-neutral-100"),
      primaryBorderColor: desaturate("--color-primary-400", "--color-neutral-400"),
      secondaryBorderColor: desaturate("--color-secondary-400", "--color-neutral-400"),
      tertiaryBorderColor: css("--color-neutral-400"),
      lineColor: css("--color-neutral-600"),
      fontFamily:
        "ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,segoe ui,Roboto,helvetica neue,Arial,noto sans,sans-serif",
      fontSize: "16px",
    },
  });
}

function initMermaidDark() {
  mermaid.initialize({
    theme: "base",
    themeVariables: {
      background: css("--color-neutral-800"),
      primaryColor: desaturate("--color-primary-700", "--color-neutral-700"),
      secondaryColor: desaturate("--color-secondary-700", "--color-neutral-700"),
      tertiaryColor: css("--color-neutral-700"),
      primaryBorderColor: desaturate("--color-primary-500", "--color-neutral-500"),
      secondaryBorderColor: desaturate("--color-secondary-500", "--color-neutral-500"),
      tertiaryBorderColor: css("--color-neutral-500"),
      lineColor: css("--color-neutral-400"),
      primaryTextColor: css("--color-neutral-100"),
      secondaryTextColor: css("--color-neutral-200"),
      tertiaryTextColor: css("--color-neutral-200"),
      textColor: css("--color-neutral-100"),
      mainBkg: css("--color-neutral-800"),
      nodeBorder: css("--color-neutral-500"),
      clusterBkg: css("--color-neutral-700"),
      titleColor: css("--color-neutral-100"),
      edgeLabelBackground: css("--color-neutral-800"),
      fontFamily:
        "ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,segoe ui,Roboto,helvetica neue,Arial,noto sans,sans-serif",
      fontSize: "16px",
    },
  });
}
