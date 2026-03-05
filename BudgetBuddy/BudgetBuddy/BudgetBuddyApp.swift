//
//  BudgetBuddyApp.swift
//  BudgetBuddy
//
//  Created by Soham Kolhatkar on 1/29/26.
//

import SwiftUI
import UIKit
import UserNotifications
import FirebaseCore
import FirebaseAuth

@main
struct BudgetBuddyApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @State private var pendingReceiptImage: UIImage?
    @State private var showReceiptFromExtension = false
    @State private var extensionReceiptViewModel = ReceiptScanViewModel()

    private let appGroupID = "group.sample.BudgetBuddy"
    private let sharedImageFilename = "receipt_pending.jpg"

    var body: some Scene {
        WindowGroup {
            ContentView()
                .preferredColorScheme(.dark)
                .task {
                    let granted = await NotificationManager.shared.requestPermission()
                    if granted {
                        NotificationManager.shared.scheduleDailyReminder(hasLoggedToday: false)
                    }
                }
                .onOpenURL { url in
                    guard url.scheme == "budgetbuddy", url.host == "receipt" else { return }
                    loadSharedReceiptImage()
                }
                .sheet(isPresented: $showReceiptFromExtension) {
                    ReceiptScanView(viewModel: extensionReceiptViewModel) {
                        showReceiptFromExtension = false
                        extensionReceiptViewModel.reset()
                    }
                }
        }
    }

    private func loadSharedReceiptImage() {
        guard let container = FileManager.default.containerURL(
            forSecurityApplicationGroupIdentifier: appGroupID
        ) else { return }

        let imageURL = container.appendingPathComponent(sharedImageFilename)
        guard let data = try? Data(contentsOf: imageURL),
              let image = UIImage(data: data) else { return }

        // Clean up shared file
        try? FileManager.default.removeItem(at: imageURL)

        extensionReceiptViewModel.reset()
        showReceiptFromExtension = true
        Task {
            await extensionReceiptViewModel.analyzeImage(image)
        }
    }
}

class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        FirebaseApp.configure()
        UNUserNotificationCenter.current().delegate = self
        requestPushNotificationPermission()
        return true
    }

    func requestPushNotificationPermission() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { granted, error in
            if granted {
                DispatchQueue.main.async {
                    UIApplication.shared.registerForRemoteNotifications()
                }
            }
            if let error {
                print("Push notification permission error: \(error)")
            }
        }
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        print("APNs device token: \(token)")

        // Register with backend
        Task {
            guard let userId = AuthManager.shared.authToken else { return }
            do {
                try await APIService.shared.registerDeviceToken(userId: userId, token: token)
                print("Device token registered with backend")
            } catch {
                print("Failed to register device token: \(error)")
            }
        }
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        print("Failed to register for remote notifications: \(error)")
    }

    // Forward remote notifications to Firebase Auth (required for phone auth)
    func application(
        _ application: UIApplication,
        didReceiveRemoteNotification userInfo: [AnyHashable: Any],
        fetchCompletionHandler completionHandler: @escaping (UIBackgroundFetchResult) -> Void
    ) {
        if Auth.auth().canHandleNotification(userInfo) {
            completionHandler(.noData)
            return
        }
        completionHandler(.noData)
    }

    // Forward URL callbacks to Firebase Auth (required for reCAPTCHA fallback)
    func application(_ app: UIApplication, open url: URL, options: [UIApplication.OpenURLOptionsKey: Any] = [:]) -> Bool {
        if Auth.auth().canHandle(url) {
            return true
        }
        return false
    }

    // Handle notifications when app is in foreground
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound, .badge])
    }

    // Handle notification taps
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let userInfo = response.notification.request.content.userInfo
        print("Notification tapped: \(userInfo)")
        completionHandler()
    }
}
