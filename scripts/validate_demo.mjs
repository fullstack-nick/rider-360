import assert from "node:assert/strict";
import { EVENT_SCHEMAS, pushValidatedEvent, validateEvent } from "../demo/data-layer/contract.mjs";

const base = {
  contract_version: "1.0.0",
  event_timestamp_ms: 1786212000000,
  synthetic_session_id: "demo-session-test",
  site_market: "DE",
};
const item = { item_id: "BIKE-COMET-16", item_name: "Comet 16", price: 329, quantity: 1 };
const layer = [];

for (const [event, required] of Object.entries(EVENT_SCHEMAS)) {
  const fields = {
    placement: "product_detail",
    size_path_version: "sp-1.0",
    question_id: "rider_height_band",
    answer_band: "110-119_cm",
    step_number: 1,
    recommended_product_id: item.item_id,
    recommendation_rank: 1,
    transaction_id: "DEMO-ORDER-001",
    currency: "EUR",
    value: 329,
    items: [item],
  };
  const payload = { ...base, event };
  for (const field of required) payload[field] = fields[field];
  assert.deepEqual(validateEvent(payload), [], `${event} should satisfy its contract`);
  pushValidatedEvent(layer, payload);
}

const piiErrors = validateEvent({
  ...base,
  event: "size_path_answer",
  question_id: "unsafe",
  answer_band: "not-used",
  step_number: 1,
  size_path_version: "sp-1.0",
  child_name: "blocked",
});
assert.match(piiErrors.join(" "), /forbidden PII-like fields/);
assert.equal(layer.length, Object.keys(EVENT_SCHEMAS).length);
console.log(`Validated ${layer.length} event schemas and the PII rejection guard.`);
