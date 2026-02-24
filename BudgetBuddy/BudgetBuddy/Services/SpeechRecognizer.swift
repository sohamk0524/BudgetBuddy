//
//  SpeechRecognizer.swift
//  BudgetBuddy
//
//  Wraps SFSpeechRecognizer + AVAudioEngine for real-time speech-to-text
//

import Foundation
import Speech
import AVFoundation

@Observable
@MainActor
class SpeechRecognizer {

    // MARK: - Public State

    var transcribedText: String = ""
    var isRecording: Bool = false
    var isAuthorized: Bool = false
    var audioLevel: Float = 0.0  // 0-1 for waveform visualization
    var error: SpeechError?

    // MARK: - Private

    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private let audioEngine = AVAudioEngine()

    // MARK: - Authorization

    func requestAuthorization() {
        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            Task { @MainActor in
                guard let self else { return }
                switch status {
                case .authorized:
                    self.isAuthorized = true
                case .denied, .restricted, .notDetermined:
                    self.isAuthorized = false
                    self.error = .notAuthorized
                @unknown default:
                    self.isAuthorized = false
                }
            }
        }
    }

    // MARK: - Recording

    func startRecording() throws {
        // Reset previous state
        recognitionTask?.cancel()
        recognitionTask = nil
        transcribedText = ""
        error = nil

        guard let speechRecognizer, speechRecognizer.isAvailable else {
            throw SpeechError.recognizerUnavailable
        }

        // Configure audio session
        let audioSession = AVAudioSession.sharedInstance()
        try audioSession.setCategory(.record, mode: .measurement, options: .duckOthers)
        try audioSession.setActive(true, options: .notifyOthersOnDeactivation)

        // Create recognition request
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true

        if speechRecognizer.supportsOnDeviceRecognition {
            request.requiresOnDeviceRecognition = true
        }

        recognitionRequest = request

        // Start recognition task
        recognitionTask = speechRecognizer.recognitionTask(with: request) { [weak self] result, error in
            Task { @MainActor in
                guard let self else { return }

                if let result {
                    self.transcribedText = result.bestTranscription.formattedString
                }

                if let error {
                    // Ignore cancellation errors
                    let nsError = error as NSError
                    if nsError.domain == "kAFAssistantErrorDomain" && nsError.code == 216 {
                        // User cancelled — not a real error
                        return
                    }
                    self.error = .recognitionFailed(error.localizedDescription)
                    self.stopRecording()
                }
            }
        }

        // Install audio tap
        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { [weak self] buffer, _ in
            self?.recognitionRequest?.append(buffer)
            let level = self?.calculateAudioLevel(buffer: buffer) ?? 0
            Task { @MainActor in
                self?.audioLevel = level
            }
        }

        audioEngine.prepare()
        try audioEngine.start()
        isRecording = true
    }

    func stopRecording() {
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionRequest = nil
        recognitionTask = nil
        isRecording = false
        audioLevel = 0

        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    // MARK: - Audio Level

    private nonisolated func calculateAudioLevel(buffer: AVAudioPCMBuffer) -> Float {
        guard let channelData = buffer.floatChannelData else { return 0 }
        let frames = buffer.frameLength
        let channelDataValue = channelData.pointee

        var sum: Float = 0
        for i in 0..<Int(frames) {
            let sample = channelDataValue[i]
            sum += sample * sample
        }

        let rms = sqrt(sum / Float(frames))
        // Normalize to 0-1 range (typical speech RMS is 0.01-0.3)
        let normalized = min(1.0, max(0.0, rms * 5.0))
        return normalized
    }
}

// MARK: - Errors

enum SpeechError: LocalizedError {
    case notAuthorized
    case recognizerUnavailable
    case recognitionFailed(String)

    var errorDescription: String? {
        switch self {
        case .notAuthorized:
            return "Speech recognition not authorized. Please enable it in Settings."
        case .recognizerUnavailable:
            return "Speech recognizer is not available on this device."
        case .recognitionFailed(let message):
            return "Recognition failed: \(message)"
        }
    }
}
