New feature: integration with Plaid

Goal: I want to integrate Plaid with BudgetBuddy so that users can link their bank accounts with BudgetBuddy. BudgetBuddy can easily access bank statments (instead of users manually downloading and uploading them). Use Plaid Api v2.

# 1. Core Integration
Use Plaid Link to link a user's bank account with BudgetBuddy. That way BudgetBuddy can pull financial data without constantly asking the user to verify/upload manually. This integration will happen *after* the user registers and takes the onboarding quiz.

# 2. Linking process
The linking process will follow a 4-step standard process:
a. Create a Link Token (/link/token/create). 
The developer's backend calls the Plaid API to create a link_token. This is temporary, secure token used to initialize - Plaid Link (the frontend module) and configure the session.

b. Initialize Link (Frontend Module)
The link_token is passed to the application's frontend, which opens the Plaid Link module. The user selects their financial institution and logs in directly with their bank credentials (or via OAuth).

c. Exchange Public Token (/item/public_token/exchange)
Once the user successfully completes the authentication, Plaid Link returns a temporary public_token to the frontend, which is then sent to the developer's backend.

d. Exchange for Access Token
The backend calls /item/public_token/exchange to swap the public_token for a permanent access_token and item_id. This access_token is used to securely fetch user data (balances, transactions) without storing bank credentials. Make sure to encrypt the access token before storing it. Make sure you document the encryption method used.

# 3. Fetch transactions for the past 6 months
After successfully linking with Plaid, we will fetch the user's transactions for the past 6 months. Fetch the user transaction data for the past 6 months and map/save this data to new `PlaidItem`, `PlaidAccount`, and `Transaction` models.

Schema changes
- Add `PlaidItem`, where you store the access token, item id, and transactions cursor.
- Add `PlaidAccount`, where you link to the PlaidItem, store balances/plaid account id
- Add `Transaction`, where you link to the PlaidAccount, and store transaction data (here the schema change is up to your judgement/Plaid best practices)


# Key Notes
- Do NOT delete any database schemas
- In general make sure changes are reverse compatible
- Do not change statment upload, we will remove it later
- Run test cases in BudgetBuddyBackend/tests to confirm that BudgetBuddy works as intended while making the changes you make
- Document schema changes clearly
- As you make changes make sure to verify them. Test them if possible.
- Ask me any clarification questions
- If I am not doing something the right way, don't hesitate to fix that or at least double check with me and make a recommendation.