Goal:

Add functionality to allow users to save (bookmark) and dislike recommendations on the Recommendations tab.

---

## Saving/Bookmarking Tips

- Users can save a recommendation by tapping a **bookmark icon** on the recommendation card. The interaction should be minimal — a single tap toggles the bookmark on/off.
- Users can **unsave** a previously saved tip by tapping the bookmark icon again (toggle behavior).
- Saved tips are accessible via a **filter/toggle on the existing Recommendations view** (e.g., "All" vs "Saved"). No separate page or tab — keep it within the current view.
- No limit on how many tips can be saved.
- Use saved tips as a signal to generate more personalized recommendations (in addition to financial data and school context).

## Disliking Tips

- Users can dislike a recommendation.
- When a user taps dislike, show a **lightweight undo toast/snackbar** (e.g., "Tip removed — Undo") rather than a confirmation dialog. This keeps the interaction fast and non-disruptive while still allowing the user to recover from accidental taps.
- Once confirmed (toast dismissed or timed out), the tip is **removed from the list with no replacement** — the list simply shrinks.
- Disliked tips are **not visible or manageable** by the user anywhere. The dislike signal is used purely behind the scenes by the recommendation engine.
- Users **cannot un-dislike** a previously disliked tip.

## Out of Scope (for now)

- No social proof or "Recommended for you" labels on tips.
- No separate saved tips page — only the filter on the Recommendations view.
- No un-dislike functionality.

---

We are adding a new way to optimize the recommendations by incorporating user preference signals (saves and dislikes) alongside existing financial data and school context.
