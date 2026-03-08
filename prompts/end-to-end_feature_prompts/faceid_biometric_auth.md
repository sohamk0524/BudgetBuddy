# Instructions for CLI: Face ID / Biometric Auth & Inactivity Timeout

**Context:**
BudgetBuddy uses Firebase Phone Auth (SMS OTP) for login. We want to avoid requiring a new SMS code every time the user opens the app, the same way banking apps work — by using Face ID / Touch ID as a fast re-authentication mechanism.

* **Current State:** Firebase phone auth works. The iOS app does not use biometrics.
* **Goal:** Add biometric lock/unlock and a 30-day inactivity timeout.

**Note:** Firebase auth middleware (`@require_auth` on backend endpoints + `APIService` Bearer token injection) is handled in a separate branch and is not part of this feature.

---

## Part 1: iOS — `AuthManager.swift` — Biometric Auth & Inactivity Timeout

### Auth State

Add `.biometricPrompt` to the `AuthState` enum:

```swift
enum AuthState: Equatable {
    case enterPhone
    case verifyOTP(phoneNumber: String)
    case biometricPrompt
    case authenticated
}
```

### New Properties

```swift
var biometricEnabled: Bool = false {
    didSet { UserDefaults.standard.set(biometricEnabled, forKey: "biometricEnabled") }
}

var isBiometricAvailable: Bool {
    let context = LAContext()
    var error: NSError?
    return context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)
}

var biometricType: String {
    let context = LAContext()
    var error: NSError?
    guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
        return "Biometrics"
    }
    switch context.biometryType {
    case .faceID:  return "Face ID"
    case .touchID: return "Touch ID"
    default:       return "Biometrics"
    }
}
```

### `init()` — Restore biometric state

```swift
init() {
    biometricEnabled = UserDefaults.standard.bool(forKey: "biometricEnabled")
    if let token = UserDefaults.standard.string(forKey: "authToken") {
        self.authToken = token
        self.userName = UserDefaults.standard.string(forKey: "userName")
        if biometricEnabled && Auth.auth().currentUser != nil {
            self.authState = .biometricPrompt
        } else {
            self.authState = .authenticated
        }
    }
}
```

### Biometric Methods

```swift
func authenticateWithBiometrics() async {
    let context = LAContext()
    var nsError: NSError?
    guard context.canEvaluatePolicy(.deviceOwnerAuthentication, error: &nsError) else {
        // No biometrics or passcode — fall back to phone auth
        await MainActor.run { self.signOut() }
        return
    }
    do {
        // .deviceOwnerAuthentication: tries Face ID/Touch ID first, auto-falls back to passcode
        try await context.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: "Unlock BudgetBuddy")
        await MainActor.run { authState = .authenticated }
        await restoreSession()
    } catch let laError as LAError {
        switch laError.code {
        case .userCancel, .appCancel, .systemCancel:
            break // Stay on lock screen
        default:
            await MainActor.run { errorMessage = "Authentication failed. Try again." }
        }
    }
}

func enableBiometrics() async -> Bool {
    let context = LAContext()
    var nsError: NSError?
    guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &nsError) else {
        return false
    }
    do {
        let success = try await context.evaluatePolicy(
            .deviceOwnerAuthenticationWithBiometrics,
            localizedReason: "Enable \(biometricType) for BudgetBuddy"
        )
        if success { await MainActor.run { biometricEnabled = true } }
        return success
    } catch { return false }
}

func disableBiometrics() { biometricEnabled = false }
```

### Inactivity Timeout (30 days)

```swift
private static let inactivityTimeoutDays: Double = 30

func recordActivity() {
    UserDefaults.standard.set(Date(), forKey: "lastActiveDate")
}

private func isSessionExpiredDueToInactivity() -> Bool {
    guard let lastActive = UserDefaults.standard.object(forKey: "lastActiveDate") as? Date else {
        return false
    }
    return Date().timeIntervalSince(lastActive) / 86400 > Self.inactivityTimeoutDays
}
```

In `restoreSession()`, add after the Firebase user guard:
```swift
if isSessionExpiredDueToInactivity() {
    await MainActor.run { self.signOut() }
    return
}
```

In `signOut()`, add: `UserDefaults.standard.removeObject(forKey: "lastActiveDate")`

In `exchangeFirebaseToken()` success block, add: `self.recordActivity()`

### Bearer Token on AuthManager's direct HTTP calls

`restoreSession()`, `completeOnboarding()`, and `deleteAccount()` make direct HTTP calls that bypass `APIService`. Add the Firebase token to each:

```swift
let idToken = try await firebaseUser.getIDToken()
var request = URLRequest(url: url)
request.setValue("Bearer \(idToken)", forHTTPHeaderField: "Authorization")
```

---

## Part 2: iOS — `BiometricUnlockView.swift` (NEW)

Create `BudgetBuddy/Views/Auth/BiometricUnlockView.swift` with two views:

### `BiometricUnlockView` — App relaunch lock screen

- Shows app logo + name + tagline centered
- "Unlock with Face ID/Touch ID" button (uses `biometricIcon` from `authManager.biometricType`)
- "Use Phone Number Instead" text button → calls `authManager.signOut()`
- Shows `authManager.errorMessage` in red if set
- `.task { await authManager.authenticateWithBiometrics() }` — auto-triggers on appear

### `BiometricSetupSheet` — Shown during onboarding

- Takes an `onComplete: () -> Void` closure
- Shows biometric icon, "Enable [biometricType]?" title
- Description: `"Unlock BudgetBuddy instantly without a verification code. Your biometric data never leaves your device — it's stored securely in your phone's Secure Enclave."`
- "Enable [biometricType]" button → `_ = await authManager.enableBiometrics(); onComplete()`
- "Skip for Now" button → `onComplete()`

---

## Part 3: iOS — `LoginView.swift` — Route biometricPrompt

Add the `.biometricPrompt` case:

```swift
case .biometricPrompt:
    BiometricUnlockView()
```

---

## Part 4: iOS — `OnboardingWizardView.swift` — Prompt biometrics after finish

After the user taps "Finish" on the last onboarding page, show `BiometricSetupSheet` before completing onboarding:

```swift
@State private var showBiometricSetup = false

// In the Finish button action:
if authManager.isBiometricAvailable {
    showBiometricSetup = true
} else {
    finishOnboarding()
}

// Sheet:
.sheet(isPresented: $showBiometricSetup) {
    BiometricSetupSheet {
        showBiometricSetup = false
        finishOnboarding()
    }
}
```

`totalPages` must equal the actual number of pages in the `TabView`:
- `isStudent ? 4 : 3` (Name, Student, School [if student], Weekly Limit)

---

## Part 5: iOS — `ProfileView.swift` — Biometric toggle in Settings

Add a biometrics section between Notifications and Linked Accounts:

```swift
Section("Security") {
    if AuthManager.shared.isBiometricAvailable {
        Toggle("\(AuthManager.shared.biometricType)", isOn: Binding(
            get: { AuthManager.shared.biometricEnabled },
            set: { newValue in
                if newValue {
                    Task { _ = await AuthManager.shared.enableBiometrics() }
                } else {
                    AuthManager.shared.disableBiometrics()
                }
            }
        ))
    }
}
```

---

## Part 6: iOS — `ContentView.swift` — Skip session restore during biometric prompt

```swift
.task {
    // Skip when biometric prompt is showing — authenticateWithBiometrics() calls
    // restoreSession() after a successful unlock.
    guard authManager.authState != .biometricPrompt else { return }
    await authManager.restoreSession()
}
```

---

## Part 7: iOS — `BudgetBuddyApp.swift` — Record activity on foreground

```swift
@Environment(\.scenePhase) private var scenePhase

// In WindowGroup body:
.onChange(of: scenePhase) { _, newPhase in
    if newPhase == .active && AuthManager.shared.isAuthenticated {
        AuthManager.shared.recordActivity()
    }
}
```

---

## Part 8: iOS — `Info.plist`

Add the Face ID usage description (required for App Store):

```xml
<key>NSFaceIDUsageDescription</key>
<string>BudgetBuddy uses Face ID to unlock your account quickly without needing a verification code.</string>
```

---

## Security Notes

- **Biometric data never touches the app.** `LocalAuthentication` only returns a boolean. All biometric processing is handled by the OS Secure Enclave.
- **`.deviceOwnerAuthentication`** (not `.deviceOwnerAuthenticationWithBiometrics`) is used for unlock — this means iOS will automatically fall back to device passcode after repeated Face ID failures, preventing lockout.
- **`.deviceOwnerAuthenticationWithBiometrics`** (biometrics only, no passcode fallback) is used for the enable-biometrics confirmation step.
- The 30-day inactivity timeout is industry-standard for financial apps. The timer resets every time the authenticated user opens the app.
- If `canEvaluatePolicy` returns false (no passcode/biometrics on device), sign out and require phone auth — never silently bypass authentication.
