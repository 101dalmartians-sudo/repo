# Homepage Content Management Enhancement - Gated Implementation Plan

Date: 2026-07-16
Execution rule: do not proceed to the next step until the current step is green.

## Step 0 (Completed): Baseline Documentation

Deliverable:
- `HOMEPAGE_BASELINE_SNAPSHOT.md`

Green criteria:
- Existing homepage flow, dynamic sources, hardcoded content, and fallbacks are documented.
- Rollback anchors are documented.

Status:
- GREEN

---

## Step 1: Data Model Design (Future-Ready + Singleton + Reuse)

Objective:
- Create a future-ready `HomepageSettings` singleton model.
- Reuse existing `HomePageContactSection` as the single contact source.
- Add inquiry persistence model with `unread/read/archived` status.

Implementation details:
- Extend `apps/news/models.py` with:
  - `HomepageSettings` (singleton configuration)
    - Hero content fields (heading, description, optional image)
    - Footer text field(s)
    - Relationship to configurable feature card entries (no hardcoded field names like card_1/card_2/card_3)
  - `HomepageFeatureCard` (FK to settings, with stable ordering)
    - `slug` or key for current cards (future extension friendly)
    - `title`, `description`, `image`, `order`, `is_active`
  - `HomepageInquiry`
    - `full_name`, `email`, `subject`, `message`, `status`, timestamps
    - statuses: `unread`, `read`, `archived`
- Keep one authoritative contact source:
  - Continue using existing `HomePageContactSection` model
  - Link `HomepageSettings` to it (OneToOne or fallback to first existing record)

Migration strategy:
- Add migrations that preserve current behavior with defaults.
- Create/ensure singleton settings record with defaults matching current homepage copy.
- Seed exactly 3 initial feature cards from current homepage strings and existing fallback image behavior.
- Do not blank any existing section.

Green criteria:
- `python manage.py makemigrations` succeeds.
- `python manage.py migrate` succeeds.
- DB has one usable `HomepageSettings` record.
- Existing contact model still authoritative and populated.
- `HomepageInquiry` model includes `archived` status.

---

## Step 2: Admin Experience (Singleton UX + Inquiries Inbox)

Objective:
- Provide simple admin management pages:
  - Homepage Settings (single shared record)
  - Feature cards under settings
  - Inquiries inbox with status workflows

Implementation details:
- In `apps/news/admin.py`:
  - Register `HomepageSettings` with singleton behavior:
    - prevent additional records after first
    - redirect list view to edit page of singleton record
  - Add inline for `HomepageFeatureCard` sorted by order.
  - Keep existing `HomePageContactSection` reuse (either inline link/reference or clearly labeled relation).
  - Register `HomepageInquiry` admin:
    - list display: submitter, subject, status, created_at
    - filters: status, created_at
    - search: full_name, email, subject, message
    - actions: mark read, mark unread, archive
    - delete enabled

Green criteria:
- Admin shows one clear Homepage Settings editor.
- Admin saves all homepage setting fields and feature cards.
- Admin inquiry filters/search/actions/delete work correctly.
- No duplicate contact source introduced.

---

## Step 3: Homepage View Wiring (No UX Change)

Objective:
- Update homepage backend context to use settings while preserving all existing functionality.

Implementation details:
- Update `apps/accounts/views.py::home` for unauthenticated branch only:
  - Load singleton `HomepageSettings` (with robust fallback if absent)
  - Continue loading `news` unchanged
  - Continue loading gallery where still needed for fallback paths
  - Resolve contact from existing authoritative source (`HomePageContactSection`)
  - Prepare feature card queryset from settings (active, ordered)
- Keep authenticated routing logic untouched.

Green criteria:
- Home view renders without errors for unauthenticated and authenticated users.
- No route/auth/dashboard behavior changed.

---

## Step 4: Template Binding With Exact Layout Preservation

Objective:
- Replace hardcoded homepage content bindings with settings-backed values while keeping HTML/CSS structure intact.

Implementation details:
- `templates/home.html`:
  - Preserve existing markup/classes/IDs and visual output.
  - Hero section pulls heading/description/image from settings; fallback to current hardcoded values/static image.
  - Feature cards render from settings cards; fallback to current gallery/default behavior.
  - Contact section continues using existing contact model values.
  - Inquiry form switched from JS-only to real POST, but same design and fields.
- `templates/base.html`:
  - Footer text sourced from settings with exact current text fallback.

Green criteria:
- Visual parity with current homepage on desktop/mobile.
- Anchors/navigation unchanged.
- Image fallbacks work when no replacement uploaded.

---

## Step 5: Inquiry Submission Backend (Simple, No Notifications)

Objective:
- Persist inquiry submissions via existing homepage form without altering design.

Implementation details:
- In `apps/accounts/views.py::home` (or dedicated lightweight handler if needed):
  - Handle POST from homepage contact form.
  - Validate required fields server-side.
  - Save `HomepageInquiry` with default status `unread`.
  - Return user-friendly response without introducing new UI design.
- Remove/replace JS console-only submission logic.
- No emails, no dashboard notifications, no background tasks.

Green criteria:
- Form submissions persist to DB every time.
- Inquiry appears in Django Admin Inquiries immediately.
- Existing homepage visual design unchanged.

---

## Step 6: Validation and Regression Checks

Objective:
- Confirm enhancement is safe and backward compatible.

Validation checklist:
- Homepage visual parity verified.
- Existing links/anchors/nav/portal access still work.
- Settings edits reflect on homepage correctly.
- Missing settings/images still show existing defaults.
- Contact source remains single and authoritative.
- Inquiries support search/filter/read/unread/archive/delete in admin.
- Existing news features unaffected.

Green criteria:
- All checks pass.
- No new critical errors reported by Django checks/tests used in this repo.

---

## Step Progress Protocol

After each step:
1. I will report exactly what changed.
2. I will run the step-specific green checks.
3. I will wait for your explicit GO before moving to the next step.
