(() => {
  const tokensInput = document.getElementById("expression-tokens");
  const preview = document.getElementById("expression-preview");
  const expressionText = document.getElementById("expression-text");
  const manualText = document.getElementById("formula-manual-text");
  if (!tokensInput || !preview) {
    return;
  }

  let tokens = [];
  try {
    const parsed = JSON.parse(tokensInput.value || "[]");
    if (Array.isArray(parsed)) {
      tokens = parsed.map((t) => String(t));
    }
  } catch (err) {
    tokens = [];
  }

  const render = () => {
    preview.textContent = tokens.join(" ");
    tokensInput.value = JSON.stringify(tokens);
    if (expressionText) {
      expressionText.value = tokens.join(" ");
    }
    if (manualText) {
      manualText.value = tokens.join(" ");
    }
  };

  const addToken = (token) => {
    const trimmed = String(token || "").trim();
    if (!trimmed) {
      return;
    }
    tokens.push(trimmed);
    render();
  };

  const setTokens = (nextTokens) => {
    tokens = Array.isArray(nextTokens) ? nextTokens.map((t) => String(t).trim()).filter(Boolean) : [];
    render();
  };

  document.querySelectorAll("[data-token]").forEach((btn) => {
    btn.addEventListener("click", () => addToken(btn.dataset.token));
  });

  document.querySelectorAll("[data-op]").forEach((btn) => {
    btn.addEventListener("click", () => addToken(btn.dataset.op));
  });

  const numberInput = document.getElementById("builder-number");
  const addNumber = document.getElementById("builder-add-number");
  if (addNumber && numberInput) {
    addNumber.addEventListener("click", () => {
      addToken(numberInput.value);
      numberInput.value = "";
      numberInput.focus();
    });
  }

  const backspace = document.getElementById("builder-backspace");
  if (backspace) {
    backspace.addEventListener("click", () => {
      tokens.pop();
      render();
    });
  }

  const clearBtn = document.getElementById("builder-clear");
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      tokens = [];
      render();
    });
  }

  const tokenizeManual = (text) => {
    const compact = String(text || "").replace(/\s+/g, "");
    if (!compact) return [];
    const matches = compact.match(/[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|[()+\-*/]/g) || [];
    if (matches.join("") !== compact) return null;
    return matches;
  };

  if (manualText) {
    manualText.addEventListener("input", () => {
      const next = tokenizeManual(manualText.value);
      if (next === null) {
        return;
      }
      tokens = next;
      tokensInput.value = JSON.stringify(tokens);
      if (expressionText) {
        expressionText.value = manualText.value;
      }
      preview.textContent = tokens.join(" ");
    });
  }

  const quickLeft = document.getElementById("quick-left-token");
  const quickOp = document.getElementById("quick-op");
  const quickRight = document.getElementById("quick-right-token");
  const quickPreview = document.getElementById("quick-op-preview");
  const quickApply = document.getElementById("quick-apply-op");
  const quickApplyPct = document.getElementById("quick-apply-pct");

  const quickTokens = (withPercent) => {
    const left = quickLeft ? String(quickLeft.value || "").trim() : "";
    const op = quickOp ? String(quickOp.value || "").trim() : "/";
    const right = quickRight ? String(quickRight.value || "").trim() : "";
    if (!left || !right) {
      return [];
    }
    const base = [left, op, right];
    if (!withPercent) {
      return base;
    }
    return ["(", ...base, ")", "*", "100"];
  };

  const renderQuickPreview = () => {
    if (!quickPreview) return;
    const base = quickTokens(false);
    if (!base.length) {
      quickPreview.textContent = "A / B";
      return;
    }
    quickPreview.textContent = base.join(" ");
  };

  [quickLeft, quickOp, quickRight].forEach((el) => {
    if (el) {
      el.addEventListener("change", renderQuickPreview);
    }
  });

  if (quickApply) {
    quickApply.addEventListener("click", () => {
      const next = quickTokens(false);
      if (!next.length) return;
      setTokens(next);
    });
  }

  if (quickApplyPct) {
    quickApplyPct.addEventListener("click", () => {
      const next = quickTokens(true);
      if (!next.length) return;
      setTokens(next);
    });
  }

  render();
  renderQuickPreview();
})();
