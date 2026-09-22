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

// accepted: https://buy.stripe.com/test_123
// accepted: https://billing.stripe.com/p/login/test_123
// rejected: http://buy.stripe.com/test_123
// rejected: https://example.test/checkout
// rejected: javascript:alert(1)
configurePaymentPage(document, window.PAYMENT_PAGE_CONFIG);
