(() => {
  const tokensInput = document.getElementById("expression-tokens");
  const preview = document.getElementById("expression-preview");
  const expressionText = document.getElementById("expression-text");
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
  };

  const addToken = (token) => {
    const trimmed = String(token || "").trim();
    if (!trimmed) {
      return;
    }
    tokens.push(trimmed);
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

  render();
})();
