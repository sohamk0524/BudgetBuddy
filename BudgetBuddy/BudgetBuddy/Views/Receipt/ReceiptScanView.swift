//
//  ReceiptScanView.swift
//  BudgetBuddy
//
//  Entry sheet for receipt scanning: camera, photo library, or Share Extension.
//

import SwiftUI
import PhotosUI

@MainActor
struct ReceiptScanView: View {
    @Bindable var viewModel: ReceiptScanViewModel
    let onDismiss: () -> Void

    @State private var showCamera = false
    @State private var showPhotosPicker = false
    @State private var selectedPhotoItem: PhotosPickerItem?

    var body: some View {
        NavigationStack {
            content
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.appBackground)
                .navigationTitle("Scan Receipt")
                .navigationBarTitleDisplayMode(.inline)
                .toolbarColorScheme(.dark, for: .navigationBar)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { onDismiss() }
                            .foregroundStyle(Color.textSecondary)
                    }
                }
        }
        .onChange(of: selectedPhotoItem) { _, newItem in
            guard let item = newItem else { return }
            Task {
                if let data = try? await item.loadTransferable(type: Data.self),
                   let image = UIImage(data: data) {
                    await viewModel.analyzeImage(image)
                }
            }
        }
        .fullScreenCover(isPresented: $showCamera) {
            CameraImagePicker { image in
                showCamera = false
                Task { await viewModel.analyzeImage(image) }
            } onCancel: {
                showCamera = false
            }
            .ignoresSafeArea()
        }
    }

    @ViewBuilder
    private var content: some View {
        switch viewModel.state {
        case .idle:
            idleView
        case .analyzing:
            analyzingView
        case .reviewed:
            if let result = viewModel.analysisResult {
                ReceiptLineItemsView(result: result) { category, items, date, merchant in
                    Task {
                        await viewModel.confirmAndAttach(
                            category: category,
                            items: items,
                            date: date,
                            merchant: merchant
                        )
                    }
                }
            }
        case .attaching:
            analyzingView  // Reuse spinner with different label
        case .done:
            doneView
        case .error(let msg):
            errorView(msg)
        }
    }

    private var idleView: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "receipt")
                .font(.system(size: 60))
                .foregroundStyle(Color.accent)

            Text("Scan a Receipt")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("Claude will extract line items from your receipt.")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)

            Spacer()

            VStack(spacing: 12) {
                Button {
                    showCamera = true
                } label: {
                    Label("Take Photo", systemImage: "camera.fill")
                        .font(.roundedHeadline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(Color.accent)
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                }

                PhotosPicker(
                    selection: $selectedPhotoItem,
                    matching: .images,
                    photoLibrary: .shared()
                ) {
                    Label("Choose from Library", systemImage: "photo.on.rectangle")
                        .font(.roundedHeadline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(Color.surface)
                        .foregroundStyle(Color.accent)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                }
            }
            .padding(.horizontal)
            .padding(.bottom, 32)
        }
    }

    @ViewBuilder
    private var analyzingView: some View {
        if viewModel.state == .attaching {
            // Simple spinner — attaching is just a quick DB write
            VStack(spacing: 20) {
                Spacer()
                ProgressView()
                    .scaleEffect(1.5)
                    .tint(Color.accent)
                Text("Saving your receipt...")
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.textPrimary)
                Spacer()
            }
        } else {
            ReceiptLoadingView(
                isBackendDone: viewModel.analysisIsComplete,
                onAllStepsDone: { viewModel.finishAnalysis() }
            )
        }
    }

    private var doneView: some View {
        VStack(spacing: 20) {
            Spacer()
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 60))
                .foregroundStyle(Color.accent)
            Text("Receipt Saved")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)
            if let resp = viewModel.attachResponse {
                Text(resp.source == "plaid" ? "Matched to an existing transaction." : "Added as a new transaction.")
                    .font(.roundedBody)
                    .foregroundStyle(Color.textSecondary)
            }
            Spacer()
            Button("Done") { onDismiss() }
                .font(.roundedHeadline)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(Color.accent)
                .foregroundStyle(.white)
                .clipShape(RoundedRectangle(cornerRadius: 14))
                .padding(.horizontal)
                .padding(.bottom, 32)
        }
    }

    private func errorView(_ message: String) -> some View {
        VStack(spacing: 20) {
            Spacer()
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 50))
                .foregroundStyle(Color.danger)
            Text("Something went wrong")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)
            Text(message)
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            Spacer()
            Button("Try Again") { viewModel.reset() }
                .font(.roundedHeadline)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(Color.surface)
                .foregroundStyle(Color.accent)
                .clipShape(RoundedRectangle(cornerRadius: 14))
                .padding(.horizontal)
                .padding(.bottom, 32)
        }
    }
}

// MARK: - Receipt Loading View

private struct LoadingStep {
    let icon: String
    let label: String
}

struct ReceiptLoadingView: View {
    /// Set to true when the backend API call has returned successfully.
    let isBackendDone: Bool
    /// Called once all steps have been checked off, so the parent can transition.
    let onAllStepsDone: () -> Void

    private let steps: [LoadingStep] = [
        LoadingStep(icon: "viewfinder",            label: "Scanning image"),
        LoadingStep(icon: "mappin.and.ellipse",    label: "Reading merchant & date"),
        LoadingStep(icon: "list.bullet.rectangle", label: "Extracting line items"),
        LoadingStep(icon: "tag",                   label: "Categorizing expenses"),
    ]

    @State private var currentStep = 0
    @State private var iconScale: CGFloat = 0.7
    @State private var iconOpacity: Double = 0
    @State private var isFastDraining = false
    @State private var hasFiredTransition = false

    var body: some View {
        VStack(spacing: 32) {
            Spacer()

            // Animated icon
            ZStack {
                Circle()
                    .fill(Color.accent.opacity(0.12))
                    .frame(width: 90, height: 90)
                let safeIcon = currentStep < steps.count ? steps[currentStep].icon : "checkmark.circle.fill"
                Image(systemName: safeIcon)
                    .font(.system(size: 34, weight: .medium))
                    .foregroundStyle(Color.accent)
                    .scaleEffect(iconScale)
                    .opacity(iconOpacity)
            }

            // Step labels
            VStack(spacing: 12) {
                ForEach(Array(steps.enumerated()), id: \.offset) { index, step in
                    HStack(spacing: 10) {
                        ZStack {
                            if index < currentStep {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundStyle(Color.accent)
                                    .font(.system(size: 18))
                            } else if index == currentStep {
                                ProgressView()
                                    .scaleEffect(0.75)
                                    .tint(Color.accent)
                                    .frame(width: 18, height: 18)
                            } else {
                                Circle()
                                    .strokeBorder(Color.textSecondary.opacity(0.3), lineWidth: 1.5)
                                    .frame(width: 18, height: 18)
                            }
                        }
                        .frame(width: 20)

                        Text(step.label)
                            .font(.roundedBody)
                            .foregroundStyle(
                                index < currentStep  ? Color.textSecondary :
                                index == currentStep ? Color.textPrimary :
                                                       Color.textSecondary.opacity(0.5)
                            )
                            .animation(.easeInOut(duration: 0.3), value: currentStep)

                        Spacer()
                    }
                }
            }
            .padding(.horizontal, 40)

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onAppear { startAnimation() }
        .onChange(of: isBackendDone) { _, done in
            if done && !isFastDraining { beginFastDrain() }
        }
    }

    // MARK: - Animation helpers

    private func startAnimation() {
        currentStep = 0
        animateIconIn()
        scheduleNextStep(delay: 1.6)
    }

    private func animateIconIn() {
        iconScale = 0.7; iconOpacity = 0
        withAnimation(.spring(duration: 0.4)) { iconScale = 1.0; iconOpacity = 1.0 }
    }

    /// Normal cadence — slow steps while waiting for backend.
    private func scheduleNextStep(delay: Double) {
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
            guard !isFastDraining else { return }
            let next = currentStep + 1
            if next < steps.count {
                withAnimation(.easeInOut(duration: 0.25)) { currentStep = next }
                animateIconIn()
                scheduleNextStep(delay: 1.6)
            } else {
                // Stay on last step until backend finishes
                scheduleNextStep(delay: 1.6)
            }
        }
    }

    /// Backend done — fast-forward remaining unchecked steps at 0.5 s each, then transition.
    private func beginFastDrain() {
        isFastDraining = true
        drainStep()
    }

    private func drainStep() {
        let next = currentStep + 1
        guard next <= steps.count else {
            // currentStep is already past the last step — fire transition once
            if !hasFiredTransition {
                hasFiredTransition = true
                onAllStepsDone()
            }
            return
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            withAnimation(.easeInOut(duration: 0.2)) { currentStep = next }
            // Only animate the icon when still within bounds
            if next < steps.count { animateIconIn() }
            drainStep()
        }
    }
}

// MARK: - Camera image picker wrapper

struct CameraImagePicker: UIViewControllerRepresentable {
    let onCapture: (UIImage) -> Void
    let onCancel: () -> Void

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = .camera
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(onCapture: onCapture, onCancel: onCancel) }

    class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let onCapture: (UIImage) -> Void
        let onCancel: () -> Void
        init(onCapture: @escaping (UIImage) -> Void, onCancel: @escaping () -> Void) {
            self.onCapture = onCapture
            self.onCancel = onCancel
        }

        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            if let image = info[.originalImage] as? UIImage {
                onCapture(image)  // onCapture sets showCamera = false — SwiftUI dismisses the cover
            }
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            onCancel()  // sets showCamera = false via SwiftUI binding
        }
    }
}

