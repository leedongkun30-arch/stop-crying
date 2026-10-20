import Foundation
import Vision
import ImageIO

// Pixel coordinates, top-left origin. Boxes are proposals, never glyph masks.
guard CommandLine.arguments.count == 3 else {
    fputs("Usage: detect_text INPUT_IMAGE OUTPUT_JSON\n", stderr); exit(2)
}
let input = URL(fileURLWithPath: CommandLine.arguments[1])
let output = URL(fileURLWithPath: CommandLine.arguments[2])
guard !FileManager.default.fileExists(atPath: output.path) else {
    fputs("Refusing to overwrite output\n", stderr); exit(2)
}
do {
    guard let source = CGImageSourceCreateWithURL(input as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        throw NSError(domain: "ImageRead", code: 1)
    }
    let started = Date()
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    try handler.perform([request])
    let width = Double(image.width), height = Double(image.height)
    let boxes: [[String: Any]] = (request.results ?? []).compactMap { observation in
        guard let text = observation.topCandidates(1).first else { return nil }
        let r = observation.boundingBox
        return ["text": text.string, "confidence": text.confidence,
                "box": [r.minX * width, (1 - r.maxY) * height,
                        r.maxX * width, (1 - r.minY) * height]]
    }
    let result: [String: Any] = ["width": image.width, "height": image.height,
        "coordinate_system": "top-left pixels", "engine": "Apple Vision accurate",
        "seconds": Date().timeIntervalSince(started), "boxes": boxes]
    try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys]).write(to: output, options: .withoutOverwriting)
    print("Detected \(boxes.count) text regions in \(String(format: "%.3f", Date().timeIntervalSince(started))) seconds")
} catch {
    fputs("\(error)\n", stderr); exit(1)
}
