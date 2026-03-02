//
//  ShareViewController.swift
//  BudgetBuddyShareExtension
//
//  Handles receipt images shared from Photos or other apps.
//  Saves the image to the App Group shared container, then opens the main app.
//

import UIKit
import Social
import MobileCoreServices
import UniformTypeIdentifiers

class ShareViewController: SLComposeServiceViewController {

    private let appGroupID = "group.sample.BudgetBuddy"
    private let sharedImageFilename = "receipt_pending.jpg"

    override func isContentValid() -> Bool { true }

    override func didSelectPost() {
        guard let item = extensionContext?.inputItems.first as? NSExtensionItem,
              let attachments = item.attachments else {
            extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
            return
        }

        let imageType = UTType.image.identifier

        for provider in attachments {
            if provider.hasItemConformingToTypeIdentifier(imageType) {
                provider.loadItem(forTypeIdentifier: imageType, options: nil) { [weak self] data, _ in
                    guard let self else { return }
                    var image: UIImage?

                    if let url = data as? URL, let loaded = UIImage(contentsOfFile: url.path) {
                        image = loaded
                    } else if let uiImage = data as? UIImage {
                        image = uiImage
                    } else if let imgData = data as? Data {
                        image = UIImage(data: imgData)
                    }

                    if let image, let jpeg = image.jpegData(compressionQuality: 0.85) {
                        if let container = FileManager.default.containerURL(
                            forSecurityApplicationGroupIdentifier: self.appGroupID
                        ) {
                            let dest = container.appendingPathComponent(self.sharedImageFilename)
                            try? jpeg.write(to: dest)
                        }
                    }

                    DispatchQueue.main.async {
                        // Open main app via URL scheme
                        if let url = URL(string: "budgetbuddy://receipt") {
                            self.extensionContext?.open(url, completionHandler: nil)
                        }
                        self.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
                    }
                }
                return
            }
        }

        extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
    }

    override func configurationItems() -> [Any]! { [] }
}
