
# Overall feedback (all phases)
Positives:
1. People consistently loved how simple the UI/UX was. It was very easy to accomplish tasks. 
2. As we improved the recommendations page they loved it as a core feature of the app. 
3. Transaction logging was straightforward, especially after adding support for manual logging and receipt scanning.

Negatives:
1. People are hesitant to link their bank account to an app with no track record.
2. People say they might not be consistent with manual logging.

# Phase 1

#### What people liked:
- Clear core purpose: people easily identified it as a tool to manage spending and find local deals
- Transaction logging was straightforward: the voice logging was relatively easy to use
- UI quality: the app was visually appealing and felt polished

#### What people *didn't* like:
- No visual breakdown: people expected a visual breakdown of spending
- Weak AI recommendations: the recommendations were wordy and buggy. They didn't feel personalized or high-value.
- No option to set spending limit
- No manual way to add transactions
- Hesitant to trust AI with financial data

#### Changes we implemented
- Added a manual method for logging transactions
- Added an option to set a spending limit during the onboarding
- Asked users if they were students/what school they went to, which we used in a RAG pipeline to get personalized, local deals
- Made the recommendations less wordy and only kept one button for generating recommendations

# Phase 2

#### What people liked:
- Deal discovery feature: people liked that the core feature was finding personalized deals around Davis. <u>This is the main feature that would draw them to the app</u>
- Expense logging: people liked having both voice and manual logging. The transaction swiping was engaging.
- Simple workflow: only two tabs, with clear core features per tab.
- AI was more trustworthy: people recognized the places/deals from the recommendations, leading to greater perceived trust in the tips tab.

#### What people *didn't* like:
- Recommendations still felt generic: (e.g. students already know to meal prep instead of eating out)
- Recommendations were still wordy: all people wanted was the deal/place and how much they would be saving.
- People wanted more support for transactions where they bought multiple items (particularly grocery shopping)

#### Changes we implemented
- Added support to upload receipts and automatically scrape transactions from that
- Shortened the recommendations to just three parts: where they are overspending + deal to address that + how much they would be saving
- Setup recommendation templates to avoid generic advice (e.g. make sure there is an alternative instead of just not doing something)

# Phase 3

#### What people liked:
- Clear app framing: financial insight app with personalized recommendations to save money.
- Easy transaction logging (same as before)
- Simple but professional UI (same as before)
- Trusted and concise recommendations: personalized, useful, and to-the-point

#### What people *didn't* like:
- Trust with financial data: people are hesitant to link their bank account without the app having a track record
- It was difficult to find the "safe to spend quota"
- Users say they might not be consistent with logging transactions
- Recommendations should have an option to expand for more info
- Transactions should have option to log store + specific items

#### Changes we plan to implement:
- Add option to expand recommendations for more info (e.g. links)
- Make the "safe to spend" number more clear
- Maybe gamify the app to give users an incentive to come back everyday (e.g. weekly saving challenges). This is the most important consideration.