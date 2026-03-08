**Goal**

Add an inline expandable detail view to recommendation cards. When a recommendation has actionable details (e.g., a specific deal or alternative), users can tap to expand the card and see more information without navigating away.

---

**Expandability: which recommendations get a detail view?**

Not every recommendation should be expandable. The backend determines expandability by the presence of detail fields — if any detail fields (`steps`, `spendingContext`, `timeHorizon`, `link`, `linkTitle`) are populated, the card is expandable. If none are populated, it is not.

Examples that SHOULD have details:
- Specific restaurant alternatives ("Try Taqueria Davis for $8 burritos")
- Weekly/recurring deals ("$5 pitchers at [bar] every Tuesday")
- Student ID discounts
- Subscription cancellation suggestions

Examples that should NOT:
- "You're on track with your budget this week"
- "You have $X left to spend"
- Generic encouragement or status updates

---

**Data model changes**

Add the following **optional** fields to `RecommendationItem` (iOS) and the backend recommendation JSON schema. All fields are optional — omit them entirely for non-expandable recommendations.

```
steps: [String]?           // 1-3 actionable steps. Short imperative sentences.
                           // e.g. ["Show your student ID at the register", "Order the lunch combo for $6.99"]

spendingContext: String?   // One short phrase referencing the user's real data.
                           // e.g. "You spent $52 at Chipotle this month (4 visits)"
                           // Max ~60 chars. Must reference a real number from their transactions.

timeHorizon: String?       // When/how often the deal applies. Omit if unsure.
                           // e.g. "Every Tuesday", "Weekdays 11am-2pm", "One-time", "Ongoing"

link: String?              // URL to a relevant page (deal page, restaurant site, etc.)
linkTitle: String?          // Display text for the link button. e.g. "View Menu", "See Deal"
                           // Defaults to "Learn More" on the frontend if link is present but linkTitle is omitted.
```

---

**Backend changes**

Files to modify:
- `BudgetBuddyBackend/services/recommendations_generator.py` — Update `RECOMMENDATIONS_SYSTEM_PROMPT` to include the new optional fields in the output JSON schema. Add instructions: "Include detail fields (`steps`, `spendingContext`, `timeHorizon`, `link`, `linkTitle`) only for recommendations where the user can take a specific action or visit a specific place. Omit all detail fields for status/tracking recommendations."
- `BudgetBuddyBackend/services/recommendation_templates.py` — Update the `food_spending_template` return dict to include `steps` and `spendingContext` derived from the analysis data it already computes (e.g., merchant breakdown, total spend). If `_get_school_food_tip` found a specific restaurant, include a `link` (search URL or restaurant URL from Tavily results) and `steps`.
- No API endpoint changes needed — the existing JSON response just gains optional fields.

The `search_local_deals` tool already returns URLs in its results. The LLM prompt should instruct the agent to include the most relevant URL as `link` when recommending a specific place or deal.

---

**iOS changes**

Files to modify:

1. **`BudgetBuddy/BudgetBuddy/Models.swift`** — Add the optional fields to `RecommendationItem`:
   ```swift
   let steps: [String]?
   let spendingContext: String?
   let timeHorizon: String?
   let link: String?
   let linkTitle: String?
   ```

2. **`BudgetBuddy/BudgetBuddy/Views/RecommendationsView.swift`** — Modify `RecommendationCardView`:

   - Add `@State private var isExpanded = false` to the card.
   - The card is tappable only if any detail field is non-nil. Compute `var isExpandable: Bool` from checking if at least one of `steps`, `spendingContext`, `timeHorizon`, `link` is non-nil.
   - When expandable, show a small chevron (`chevron.right` that rotates to `chevron.down` when expanded) on the trailing edge of the card.
   - On tap, toggle `isExpanded` with animation (`.spring(response: 0.3, dampingFraction: 0.8)`).
   - When expanded, show a `VStack` below the existing card content (inside the same card background) containing:
     1. **Spending context** (if present): A single line of secondary text, styled like the existing description but slightly dimmer.
     2. **Steps** (if present): Numbered list (`1.`, `2.`, `3.`) in secondary text. Keep styling minimal — no bullet icons needed.
     3. **Time horizon** (if present): A small capsule/pill badge (similar style to the existing "Save ~$X" badge but using a neutral/secondary color like `Color.textSecondary.opacity(0.15)`).
     4. **Link** (if present): A `Link(linkTitle ?? "Learn More", destination: url)` styled as a small tappable text button in accent color. This opens in Safari (using SwiftUI's built-in `Link` — no UIKit needed).
   - Use a `Divider` between the existing card content and the expanded section.
   - Animate the expand/collapse with `.clipShape(RoundedRectangle)` and a matched transition so the card grows smoothly.

---

**Constraints**
- SwiftUI only — no UIKit.
- Use `@Observable` / `@State`, not `ObservableObject`.
- Rounded font design (`.rounded`) for all text — match existing `Theme.swift` usage.
- Dark mode compatible — use existing color tokens (`Color.textPrimary`, `Color.textSecondary`, `Color.accent`, `Color.surface`, etc.).
- No new dependencies.
