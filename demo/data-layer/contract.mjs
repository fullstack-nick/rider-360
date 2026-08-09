export const CONTRACT_VERSION = "1.0.0";

export const EVENT_SCHEMAS = Object.freeze({
  size_path_cta_impression: ["placement", "size_path_version"],
  size_path_start: ["placement", "size_path_version"],
  size_path_answer: ["question_id", "answer_band", "step_number", "size_path_version"],
  size_path_complete: ["recommended_product_id", "size_path_version"],
  size_path_recommendation: [
    "recommended_product_id",
    "recommendation_rank",
    "size_path_version",
  ],
  select_item: ["items"],
  add_to_cart: ["currency", "value", "items"],
  begin_checkout: ["currency", "value", "items"],
  purchase: ["transaction_id", "currency", "value", "items"],
});

const FORBIDDEN_KEYS = new Set([
  "address",
  "birth_date",
  "child_name",
  "email",
  "free_text",
  "full_name",
  "latitude",
  "longitude",
  "phone",
  "postal_address",
  "precise_location",
]);

function collectForbiddenKeys(value, path = "event", violations = []) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => collectForbiddenKeys(item, `${path}[${index}]`, violations));
    return violations;
  }
  if (!value || typeof value !== "object") return violations;

  for (const [key, child] of Object.entries(value)) {
    if (FORBIDDEN_KEYS.has(key.toLowerCase())) violations.push(`${path}.${key}`);
    collectForbiddenKeys(child, `${path}.${key}`, violations);
  }
  return violations;
}

export function validateEvent(payload) {
  const errors = [];
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return ["payload must be an object"];
  }
  if (typeof payload.event !== "string" || !payload.event.trim()) {
    errors.push("event must be a non-empty string");
  }
  if (payload.contract_version !== CONTRACT_VERSION) {
    errors.push(`contract_version must equal ${CONTRACT_VERSION}`);
  }
  if (!Number.isInteger(payload.event_timestamp_ms) || payload.event_timestamp_ms <= 0) {
    errors.push("event_timestamp_ms must be a positive integer");
  }
  if (typeof payload.synthetic_session_id !== "string" || !payload.synthetic_session_id) {
    errors.push("synthetic_session_id is required");
  }

  const required = EVENT_SCHEMAS[payload.event] ?? [];
  for (const field of required) {
    if (!(field in payload)) errors.push(`${field} is required for ${payload.event}`);
  }
  if ("items" in payload && (!Array.isArray(payload.items) || payload.items.length === 0)) {
    errors.push("items must be a non-empty array when provided");
  }
  if ("value" in payload && (typeof payload.value !== "number" || payload.value < 0)) {
    errors.push("value must be a non-negative number");
  }
  if ("currency" in payload && !/^[A-Z]{3}$/.test(payload.currency)) {
    errors.push("currency must be a three-letter uppercase code");
  }
  const forbidden = collectForbiddenKeys(payload);
  if (forbidden.length) errors.push(`forbidden PII-like fields: ${forbidden.join(", ")}`);
  return errors;
}

export function pushValidatedEvent(dataLayer, payload) {
  const errors = validateEvent(payload);
  if (errors.length) throw new Error(errors.join("; "));
  const immutableCopy = JSON.parse(JSON.stringify(payload));
  dataLayer.push(immutableCopy);
  return immutableCopy;
}
