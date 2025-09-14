import Foundation

enum DataLoaderError: Error {
  case fileMissing(String)
  case decoding(String)
}

final class InvoiceDataLoader {
  static let shared = InvoiceDataLoader()
  private init() {}

  // MARK: - Raw JSON Structures
  struct RawClient: Codable {
    let ro: [String: String]?
    let en: [String: String]?
    let curr: String
    let item: [String: [String: String]]
    let bonus: [String: [String: String]]?
  }
  struct RawProvider: Codable {
    let ro: [String: String]?
    let en: [String: String]?
    let curr: String
    let payment: [String: [String: String]]?
    let bonus: [String: [String: String]]?  // optional bonus similar to client
  }

  private struct ArgsMap: Codable {
    let invoiceNo: String
    let invoiceSeries: String
    let invoiceDate: String
    let dueDate: String
    let lang: String
    let qty: String
    let client: String
    let exchange: String
    let exchangeRate: String
    let total: String
    let provider: String
    let bonus: String
  }

  private lazy var bundle: Bundle = {
    // The resources are inside the executable module bundle.
    Bundle.module
  }()

  // Raw JSON text (for order preservation)
  private lazy var rawClientsJSON: String = {
    guard let url = bundle.url(forResource: "clients", withExtension: "json"),
      let data = try? Data(contentsOf: url),
      let str = String(data: data, encoding: .utf8)
    else { return "" }
    return str
  }()
  private lazy var rawProvidersJSON: String = {
    guard let url = bundle.url(forResource: "provider", withExtension: "json"),
      let data = try? Data(contentsOf: url),
      let str = String(data: data, encoding: .utf8)
    else { return "" }
    return str
  }()

  private func loadJSON<T: Decodable>(_ name: String, as type: T.Type) -> T {
    guard let url = bundle.url(forResource: name, withExtension: "json") else {
      fatalError("Missing resource: \(name).json")
    }
    do {
      let data = try Data(contentsOf: url)
      return try JSONDecoder().decode(T.self, from: data)
    } catch {
      fatalError("Decoding error for \(name): \(error)")
    }
  }

  // Public loaders
  func loadProviders() -> [String: RawProvider] {
    loadJSON("provider", as: [String: RawProvider].self)
  }
  func loadClients() -> [String: RawClient] { loadJSON("clients", as: [String: RawClient].self) }

  // MARK: - Ordered key extraction (best-effort parsing of original JSON order)
  private func orderedKeys(in json: String, entity: String, section: String) -> [String] {
    guard let entityRange = json.range(of: "\"" + entity + "\"") else { return [] }
    let afterEntity = json[entityRange.lowerBound...]
    guard let sectionRange = afterEntity.range(of: "\"" + section + "\"") else { return [] }
    // Find first '{' after section key
    guard let braceStart = afterEntity[sectionRange.upperBound...].firstIndex(of: "{") else {
      return []
    }
    var depth = 1
    var i = afterEntity.index(after: braceStart)
    var key: String = ""
    var inString = false
    var collected: [String] = []
    var current = ""
    while i < afterEntity.endIndex && depth > 0 {
      let ch = afterEntity[i]
      if ch == "\"" {
        if inString {
          // end string
          key = current
          current = ""
          inString = false
          // Peek ahead for ':' at depth 1
          var look = afterEntity.index(after: i)
          while look < afterEntity.endIndex && afterEntity[look].isWhitespace {
            look = afterEntity.index(after: look)
          }
          if look < afterEntity.endIndex && afterEntity[look] == ":" && depth == 1 {
            if key != "curr" && key != "payment" && key != "item" && key != "bonus" {
              collected.append(key)
            }
          }
        } else {
          inString = true
        }
      } else if inString {
        current.append(ch)
      } else if ch == "{" {
        depth += 1
      } else if ch == "}" {
        depth -= 1
      }
      i = afterEntity.index(after: i)
    }
    return collected
  }

  func orderedProviderKeys(provider: String, lang: String) -> [String] {
    orderedKeys(in: rawProvidersJSON, entity: provider, section: lang)
  }
  func orderedClientKeys(client: String, lang: String) -> [String] {
    orderedKeys(in: rawClientsJSON, entity: client, section: lang)
  }
  func orderedPaymentKeys(provider: String, lang: String) -> [String] {
    // Payment is a nested object inside provider, re-scan for payment/lang path
    guard let entityRange = rawProvidersJSON.range(of: "\"" + provider + "\"") else { return [] }
    let afterEntity = rawProvidersJSON[entityRange.lowerBound...]
    guard let paymentRange = afterEntity.range(of: "\"payment\"") else { return [] }
    guard let langRange = afterEntity[paymentRange.upperBound...].range(of: "\"" + lang + "\"")
    else { return [] }
    guard let braceStart = afterEntity[langRange.upperBound...].firstIndex(of: "{") else {
      return []
    }
    var depth = 1
    var i = afterEntity.index(after: braceStart)
    var inString = false
    var current = ""
    var keys: [String] = []
    while i < afterEntity.endIndex && depth > 0 {
      let ch = afterEntity[i]
      if ch == "\"" {
        if inString {
          let key = current
          current = ""
          inString = false
          var look = afterEntity.index(after: i)
          while look < afterEntity.endIndex && afterEntity[look].isWhitespace {
            look = afterEntity.index(after: look)
          }
          if look < afterEntity.endIndex && afterEntity[look] == ":" && depth == 1 {
            keys.append(key)
          }
        } else {
          inString = true
        }
      } else if inString {
        current.append(ch)
      } else if ch == "{" {
        depth += 1
      } else if ch == "}" {
        depth -= 1
      }
      i = afterEntity.index(after: i)
    }
    return keys
  }
  func loadArgsMap() -> [String: String] {  // flatten values
    let map = loadJSON("args", as: ArgsMap.self)
    return [
      "invoiceNo": map.invoiceNo,
      "invoiceSeries": map.invoiceSeries,
      "invoiceDate": map.invoiceDate,
      "dueDate": map.dueDate,
      "lang": map.lang,
      "qty": map.qty,
      "client": map.client,
      "exchange": map.exchange,
      "exchangeRate": map.exchangeRate,
      "total": map.total,
      "provider": map.provider,
      "bonus": map.bonus,
    ]
  }

  // Placeholder: loads bundled JSON later. For now returns mock objects.
  func loadSampleInvoice() -> Invoice {
    let providerMap: [String: String] = [
      "Name": "Sample Provider SRL",
      "Address": "Street X, City Y",
      "CUI": "RO123456",
    ]
    let clientMap: [String: String] = [
      "Name": "Client Corp",
      "Address": "Client Street, Town",
      "Country": "RO",
    ]
    func ord(_ m: [String: String]) -> [Party.FieldLine] {
      m.keys.sorted().map { .init(key: $0, value: m[$0]!, isBold: $0.hasSuffix("-B")) }
    }
    let provider = Party(name: "Provider", fields: providerMap, ordered: ord(providerMap))
    let client = Party(name: "Client", fields: clientMap, ordered: ord(clientMap))
    let items = [
      ItemLine(
        description: "Development Services", unitPrice: Money(amount: 23, currency: "GBP"),
        unit: "hour", quantity: 10, isBonus: false),
      ItemLine(
        description: "Travel expenses", unitPrice: Money(amount: 247, currency: "GBP"),
        unit: "item", quantity: 1, isBonus: true),
    ]
    return Invoice(
      series: "CTC", number: "001", issueDate: Date(),
      dueDate: Calendar.current.date(byAdding: .day, value: 30, to: Date())!, client: client,
      provider: provider, currencySource: "GBP", currencyTarget: "RON", exchangeRate: 5.90,
      items: items, language: "en", paymentLines: nil)
  }
}
