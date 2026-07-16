# Homepage Baseline Snapshot (Pre-Enhancement)

Date: 2026-07-16
Purpose: rollback reference before Homepage Content Management Enhancement.

## 1. Current Homepage Entry Point and Routing

- Root URL (`/`) resolves through `apps.accounts.urls`.
- Homepage view is `home` in `apps/accounts/views.py`.
- URL patterns currently in use:
  - `aspireacademy/urls.py`
  - `apps/accounts/urls.py`

Behavior in `home` view:
- Unauthenticated user:
  - fetches latest 5 `News`
  - fetches up to 8 active `GalleryImage` records ordered by `order`, `-created_at`
  - fetches first `HomePageContactSection` or a non-persisted default instance
  - renders `templates/home.html`
- Authenticated user:
  - routed to student/teacher/admin dashboards based on profile
  - approval checks preserved

## 2. Existing Dynamic Homepage Data Sources

### 2.1 Gallery images (already dynamic)

Model: `apps/news/models.py::GalleryImage`
- `title`
- `caption`
- `image`
- `order`
- `active`

Used in homepage for:
- Hero collage image blocks
- Feature cards section (first 5 images)

### 2.2 Contact information (already dynamic)

Model: `apps/news/models.py::HomePageContactSection`
- `section_title`
- `introductory_text`
- `phone_number`
- `email_address`
- `physical_address`
- `availability_hours`
- `form_heading`
- `form_description`

Admin registration exists in `apps/news/admin.py`.
Migration `apps/news/migrations/0003_homepagecontactsection.py` seeds a default record when absent.

## 3. Existing Hardcoded Homepage Content (Template)

File: `templates/home.html`

### 3.1 Hero textual content currently hardcoded
- Welcome label: `Welcome to`
- Title: `Aspire Academy`
- Tagline: `Inspiring Excellence Through Quality Education`
- Description: `We provide a nurturing environment where learners grow academically, socially and personally.`

### 3.2 Hero badges currently hardcoded
- `Qualified Teachers`
- `Modern Facilities`
- `Safe & Secure Environment`

### 3.3 Gallery/hero image fallbacks already present
If gallery image items are missing, template falls back to:
- static image: `static/images/home_bg.jpg`
- default overlay titles/captions

### 3.4 Feature cards behavior currently dynamic with fallback
- Primary source: `gallery_images|slice:":5"`
- Empty-state fallback card uses `static/images/home_bg.jpg` and default copy.

### 3.5 News block currently dynamic
- Uses `news` queryset from view
- Uses first attached news image when available
- Has a no-news empty state message

### 3.6 Contact block currently dynamic
- Uses `contact_section` fields from `HomePageContactSection`

### 3.7 Inquiry form currently NON-persistent
Current form:
- `onsubmit="handleSubmit(event)"`
- JavaScript prevents default submit and logs form data to browser console
- No database save, no backend endpoint, no admin inbox

## 4. Existing Footer Content

File: `templates/base.html`
- Footer marketing copy and subtext are hardcoded.
- Footer appears globally via base template inheritance.

## 5. Existing Navigation and UX Elements to Preserve

From `templates/base.html` and `templates/home.html`:
- Top navigation links and anchors:
  - Home (`/`)
  - About (`/#about`)
  - Admissions (`/#admissions`)
  - Gallery (`/#gallery`)
  - News
- Homepage section IDs in use:
  - `about`, `gallery`, `admissions`, `news`, `contact`
- Login portal cards for Student/Teacher/Admin all link to existing login flow.

## 6. Known Non-Negotiable Preservation Targets

Must remain unchanged unless explicitly approved:
- Homepage layout structure
- CSS and responsive behavior
- URL routes and authentication flow
- Portal navigation and existing links
- Existing news functionality

## 7. Rollback Notes

If any enhancement step introduces regression, rollback should restore:
- `templates/home.html` inquiry JS-only behavior
- `apps/accounts/views.py` homepage context logic as currently defined
- `templates/base.html` footer static text
- Existing `GalleryImage` and `HomePageContactSection` behavior and admin registrations
