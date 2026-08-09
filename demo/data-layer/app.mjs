import { CONTRACT_VERSION, pushValidatedEvent } from "./contract.mjs";

window.dataLayer = window.dataLayer || [];

const sessionId = "demo-session-001";
const item = Object.freeze({
  item_id: "BIKE-COMET-16",
  item_name: "Comet 16",
  item_brand: "Riderly Bikes",
  item_category: "bike",
  price: 329,
  quantity: 1,
});
const state = { step: 0, answers: {} };

const flow = [
  {
    label: "Start SizePath",
    hint: "Record an eligible CTA start—not a purchase outcome.",
    event: "size_path_start",
    fields: { placement: "product_detail", size_path_version: "sp-1.0" },
  },
  {
    label: "Answer height band",
    hint: "Use a coarse band; never collect a name, birthday, or exact height.",
    event: "size_path_answer",
    fields: {
      question_id: "rider_height_band",
      answer_band: "110-119_cm",
      step_number: 1,
      size_path_version: "sp-1.0",
    },
  },
  {
    label: "Answer riding context",
    hint: "Capture a bounded choice instead of free text.",
    event: "size_path_answer",
    fields: {
      question_id: "riding_context",
      answer_band: "mixed_paths",
      step_number: 2,
      size_path_version: "sp-1.0",
    },
  },
  {
    label: "Show recommendation",
    hint: "The recommendation is a feature output; later outcomes are joined separately.",
    event: "size_path_recommendation",
    fields: {
      recommended_product_id: item.item_id,
      recommendation_rank: 1,
      size_path_version: "sp-1.0",
      items: [item],
    },
  },
  {
    label: "Add to cart",
    hint: "Send the standard ecommerce payload with item-level detail.",
    event: "add_to_cart",
    fields: { currency: "EUR", value: 329, items: [item] },
  },
  {
    label: "Complete purchase",
    hint: "The synthetic transaction ID reconciles to the operational order source.",
    event: "purchase",
    fields: {
      transaction_id: "DEMO-ORDER-001",
      currency: "EUR",
      value: 329,
      items: [item],
    },
  },
];

const log = document.querySelector("#event-log");
const action = document.querySelector("#flow-action");
const hint = document.querySelector("#flow-hint");
const counter = document.querySelector("#event-count");
const progress = document.querySelector("#progress-bar");
const status = document.querySelector("#contract-status");

function baseEvent(event) {
  return {
    event,
    contract_version: CONTRACT_VERSION,
    event_timestamp_ms: Date.now(),
    synthetic_session_id: sessionId,
    site_market: "DE",
    page_type: "product_detail",
    consent_state: "analytics_demo_only",
  };
}

function renderEvent(payload) {
  const row = document.createElement("article");
  row.className = "event-row";
  const title = document.createElement("div");
  title.className = "event-title";
  title.innerHTML = `<span>${window.dataLayer.length.toString().padStart(2, "0")}</span><strong>${payload.event}</strong>`;
  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(payload, null, 2);
  row.append(title, pre);
  log.prepend(row);
  counter.textContent = String(window.dataLayer.length);
}

function emit(event, fields = {}) {
  const payload = pushValidatedEvent(window.dataLayer, { ...baseEvent(event), ...fields });
  renderEvent(payload);
  status.textContent = "Contract valid";
  status.dataset.state = "valid";
}

function updateFlow() {
  if (state.step >= flow.length) {
    action.textContent = "Restart demo";
    hint.textContent = "Seven validated events are now available in window.dataLayer.";
    progress.style.width = "100%";
    return;
  }
  action.textContent = flow[state.step].label;
  hint.textContent = flow[state.step].hint;
  progress.style.width = `${(state.step / flow.length) * 100}%`;
}

action.addEventListener("click", () => {
  if (state.step >= flow.length) {
    window.dataLayer.length = 0;
    log.replaceChildren();
    state.step = 0;
    counter.textContent = "0";
    status.textContent = "Ready";
    status.dataset.state = "ready";
    updateFlow();
    emit("size_path_cta_impression", {
      placement: "product_detail",
      size_path_version: "sp-1.0",
    });
    return;
  }
  const current = flow[state.step];
  emit(current.event, current.fields);
  state.step += 1;
  updateFlow();
});

document.querySelector("#pii-check").addEventListener("click", () => {
  try {
    pushValidatedEvent(window.dataLayer, {
      ...baseEvent("size_path_answer"),
      question_id: "free_form",
      answer_band: "not-used",
      step_number: 99,
      size_path_version: "sp-1.0",
      child_name: "This must never be collected",
    });
  } catch (error) {
    status.textContent = "PII payload rejected";
    status.dataset.state = "blocked";
    hint.textContent = error.message;
  }
});

emit("size_path_cta_impression", {
  placement: "product_detail",
  size_path_version: "sp-1.0",
});
updateFlow();
