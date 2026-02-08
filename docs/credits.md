# Credits System (Plan)

This document defines the minimal credits system for VidWiz.

## Rules
- New users receive 100 credits once at signup.
- Credits never expire.
- Wiz chat charges 5 credits per video per user, on conversation creation.
- AI note generation charges 1 credit when the AI note job is enqueued.
- Actions are blocked when the user has insufficient credits.
- Credits are shown on the Profile page with a "Buy more" CTA.

## Payments (Dodo)
- Checkout sessions are created via `POST /v2/payments/checkout`.
- Webhooks are handled at `POST /v2/payments/webhooks/dodo`.
- Credits are granted on `payment.succeeded` webhook events.
- Purchases are tracked in `credit_purchases` with `status=pending|completed|failed`.

### Required Environment Variables
- `DODO_PAYMENTS_API_KEY`
- `DODO_PAYMENTS_WEBHOOK_KEY`
- `DODO_PAYMENTS_ENVIRONMENT`
- `DODO_PAYMENTS_RETURN_URL`
- `DODO_CREDIT_PRODUCTS` (JSON list of credit products)

Example:
```
DODO_CREDIT_PRODUCTS='[
  {"product_id":"<ID_200>","credits":200,"name":"200 Credits","price_inr":20},
  {"product_id":"<ID_600>","credits":600,"name":"600 Credits","price_inr":50},
  {"product_id":"<ID_1500>","credits":1500,"name":"1500 Credits","price_inr":100}
]'
```

### Field Notes
- `price_inr` is validated at startup and stored in config but not used elsewhere yet.
  - Intended for UI display and optional server-side pricing validation later.


## Backend Plan
1. Data model
   - Add `users.credits_balance` (int, default `0`).
   - Add `credits_ledger` table:
     - `id`, `user_id`, `delta`, `reason`, `ref_type`, `ref_id`, `created_at`
     - Unique index on (`user_id`, `reason`, `ref_type`, `ref_id`) for idempotency.
2. Signup grant
   - On user creation (email + Google OAuth), add +100 and ledger row `reason=signup_grant`.
3. Wiz charge
   - In `POST /v2/conversations`, check if the user has already been charged for this `video_id`.
   - If not charged and balance < 5, block request with an API error.
   - Otherwise, deduct 5 and insert a ledger row with `ref_type=video_id`.
4. AI note charge
   - When the AI note job is enqueued (empty note, AI notes enabled, transcript available):
     - If balance < 1, block enqueue and return an API error.
     - Otherwise, deduct 1 and insert a ledger row.
5. API surface
   - Include `credits_balance` in `GET /v2/users/me`.
6. UI
   - Profile page shows the credits balance and a "Buy more" CTA.
7. Tests
   - Signup grants 100 once.
   - Wiz charge blocks on insufficient credits and charges once per video.
   - AI note enqueue blocks on insufficient credits.
   - Ledger idempotency.
