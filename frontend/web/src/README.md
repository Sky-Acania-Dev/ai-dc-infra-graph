# Frontend Source Layout

The current React app is intentionally small, but the scaffold reserves these folders for the next growth step:

- `components/`: reusable UI pieces such as maps, panels, tables, and overlays.
- `views/`: route/page-level screens. Validation and topology screens should move here as they become larger.
- `hooks/`: reusable React hooks for API loading, selection state, settings, and browser persistence.
- `i18n/`: localization tables, locale formatting helpers, and future translation utilities.
- `lib/`: non-React helpers such as API clients, topology transforms, and color utilities.
- `styles/`: split CSS files when `styles.css` becomes too large.

Keep domain codes from the backend unchanged in UI state. Localize display labels and enum values only.
