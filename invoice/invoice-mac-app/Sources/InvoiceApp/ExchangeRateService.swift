import Foundation

actor ExchangeRateService {
  static let shared = ExchangeRateService()
  private let session: URLSession = .shared

  private func apiKey() -> String? {
    guard let url = Bundle.module.url(forResource: "APIKEY", withExtension: "txt"),
      let key = try? String(contentsOf: url).trimmingCharacters(in: .whitespacesAndNewlines),
      !key.isEmpty, !key.contains("REPLACE_WITH")
    else { return nil }
    return key
  }

  struct RateError: Error, LocalizedError {
    let message: String
    var errorDescription: String? { message }
  }

  func fetchRate(from: String, to: String) async throws -> Double {
    guard let key = apiKey() else { throw RateError(message: "Missing API key.") }
    let base = URL(string: "https://v6.exchangerate-api.com/v6/\(key)/latest/\(from)")!
    let (data, response) = try await session.data(from: base)
    guard (response as? HTTPURLResponse)?.statusCode == 200 else {
      throw RateError(message: "HTTP error")
    }
    let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
    if let conv = json?["conversion_rates"] as? [String: Any], let value = conv[to] as? Double {
      return value
    }
    throw RateError(message: "Rate not found")
  }
}
