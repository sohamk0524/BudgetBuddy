//
//  ReceiptScanView.swift
//  BudgetBuddy
//
//  Entry sheet for receipt scanning: camera, photo library, or Share Extension.
//

import SwiftUI
import PhotosUI

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
                ReceiptLineItemsView(result: result) { essentialTotal, discretionaryTotal in
                    let today = DateFormatter.isoDate.string(from: Date())
                    let date = result.date ?? today
                    Task {
                        await viewModel.confirmAndAttach(
                            date: date,
                            essentialTotal: essentialTotal,
                            discretionaryTotal: discretionaryTotal
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

            Text("Claude will extract line items and classify what's essential vs fun money.")
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

    private var analyzingView: some View {
        VStack(spacing: 20) {
            Spacer()
            ProgressView()
                .scaleEffect(1.5)
                .tint(Color.accent)
            Text(viewModel.state == .attaching ? "Saving your receipt..." : "Reading your receipt...")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)
            Spacer()
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

// MARK: - Camera image picker wrapper

struct CameraImagePicker: UIViewControllerRepresentable {
    let onCapture: (UIImage) -> Void

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = .camera
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(onCapture: onCapture) }

    class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let onCapture: (UIImage) -> Void
        init(onCapture: @escaping (UIImage) -> Void) { self.onCapture = onCapture }

        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            if let image = info[.originalImage] as? UIImage {
                onCapture(image)
            }
            picker.dismiss(animated: true)
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            picker.dismiss(animated: true)
        }
    }
}

// MARK: - DateFormatter helper

private extension DateFormatter {
    static let isoDate: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
}
