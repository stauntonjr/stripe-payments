function isAllowedStripeUrl(value) {
  try {
    const url = new URL(value);
    return (
      url.protocol === "https:" &&
      (url.hostname === "buy.stripe.com" ||
        url.hostname === "billing.stripe.com")
    );
  } catch {
    return false;
  }
}

function configurePaymentPage(document, config) {
  const unavailable = [];

  for (const [id, value] of Object.entries(config)) {
    const action = document.getElementById(id);
    if (!action) continue;

    if (isAllowedStripeUrl(value)) {
      action.href = value;
      action.removeAttribute("aria-disabled");
    } else {
      action.removeAttribute("href");
      action.setAttribute("aria-disabled", "true");
      action.title = "This Stripe test checkout has not been configured yet.";
      unavailable.push(id);
    }
  }

  const status = document.getElementById("configuration-status");
  if (status) {
    status.hidden = unavailable.length === 0;
  }
}

function isAllowedCheckoutUrl(value) {
  try {
    const url = new URL(value);
    return (
      url.protocol === "https:" &&
      url.hostname === "checkout.stripe.com" &&
      url.username === "" &&
      url.password === ""
    );
  } catch {
    return false;
  }
}

function setTickerPulseBusy(button, error, busy) {
  button.disabled = busy;
  if (busy) {
    button.setAttribute("aria-busy", "true");
    error.hidden = true;
    error.textContent = "";
  } else {
    button.removeAttribute("aria-busy");
  }
}

function configureTickerPulseCheckout(document, window) {
  const button = document.getElementById("tickerPulseCheckoutButton");
  const error = document.getElementById("tickerPulseCheckoutError");
  if (!button || !error) return;

  button.addEventListener("click", async () => {
    setTickerPulseBusy(button, error, true);
    let redirecting = false;
    try {
      const response = await fetch("/api/checkout-sessions", {
        method: "POST",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("checkout request failed");
      const payload = await response.json();
      if (!isAllowedCheckoutUrl(payload.checkout_url)) {
        throw new Error("unsafe checkout destination");
      }
      window.location.assign(payload.checkout_url);
      redirecting = true;
    } catch {
      error.textContent = "Checkout is temporarily unavailable. Please try again.";
      error.hidden = false;
    } finally {
      if (!redirecting) setTickerPulseBusy(button, error, false);
    }
  });
}

function configureCheckoutReturn(document, window) {
  const status = document.getElementById("configuration-status");
  if (!status) return;

  const outcome = new URLSearchParams(window.location.search || "").get("checkout");
  if (outcome === "success") {
    status.textContent =
      "Subscription checkout completed. Your payment is being confirmed.";
    status.hidden = false;
  } else if (outcome === "tip-success") {
    status.textContent =
      "Thank you for your tip. Stripe has confirmed your checkout.";
    status.hidden = false;
  } else if (outcome === "cancelled") {
    status.textContent = "Checkout was cancelled. No payment was made.";
    status.hidden = false;
  }
}

// accepted: https://buy.stripe.com/test_123
// accepted: https://billing.stripe.com/p/login/test_123
// rejected: http://buy.stripe.com/test_123
// rejected: https://example.test/checkout
// rejected: javascript:alert(1)
configurePaymentPage(document, window.PAYMENT_PAGE_CONFIG);
configureTickerPulseCheckout(document, window);
configureCheckoutReturn(document, window);
