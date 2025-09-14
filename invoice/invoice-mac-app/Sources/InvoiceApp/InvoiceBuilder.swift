import Foundation
import SwiftUI

@MainActor
final class InvoiceBuilder: ObservableObject {
  // Aggregated state container
  struct Draft: Codable, Equatable {
    var invoiceSeries: String = "CTC"
    var invoiceNo: String = "001"
    var issueDate: Date = Date()
    var dueDate: Date = Calendar.current.date(byAdding: .day, value: 30, to: Date())!
    var language: String = "en"
    var quantity: Double = 1
    var selectedClientKey: String = "Balloon"
    var selectedProviderKey: String = "CTC"
    var useExchange: Bool = true
    var customExchangeRate: String = ""
    var customTotal: String = ""
    var includeBonus: Bool = false
    var fetchingRate: Bool = false
    var errorMessage: String? = nil
  }

  @Published private(set) var draft: Draft = Draft()
  // Cached invoice to avoid triggering extra publishes from external @State
  private var cachedInvoiceValue: Invoice? = nil
  private var cachedDraftSnapshot: Draft? = nil

  private let defaultsKey = "InvoiceBuilderStateV1"
  private var cancellables: [Any] = []

  // Loaded data
  private(set) var rawClients: [String: InvoiceDataLoader.RawClient] = [:]
  private(set) var rawProviders: [String: InvoiceDataLoader.RawProvider] = [:]

  init() {
    loadData()
    restore()
    let _ = objectWillChange.sink { _ in
      debugPublish("InvoiceBuilder", "objectWillChange emitted")
    }
  }

  // MARK: - Mutation helper
  private func mutate(_ block: (inout Draft) -> Void) {
    var snap = draft
    block(&snap)
    guard snap != draft else { return }
    draft = snap
    debugPublish("InvoiceBuilder", "draft mutated")
  }

  // MARK: - Data loading / apply
  func loadData() {
    rawClients = InvoiceDataLoader.shared.loadClients()
    rawProviders = InvoiceDataLoader.shared.loadProviders()
    DispatchQueue.main.async { [rawClients, rawProviders, weak self] in
      self?.mutate { d in
        if rawClients[d.selectedClientKey] == nil {
          d.selectedClientKey = rawClients.keys.sorted().first ?? ""
        }
        if rawProviders[d.selectedProviderKey] == nil {
          d.selectedProviderKey = rawProviders.keys.sorted().first ?? ""
        }
      }
      debugPublish(
        "InvoiceBuilder",
        "applyData start/end (client=\(self?.draft.selectedClientKey ?? "?"), provider=\(self?.draft.selectedProviderKey ?? "?"))"
      )
    }
  }

  func applyData(
    clients: [String: InvoiceDataLoader.RawClient],
    providers: [String: InvoiceDataLoader.RawProvider]
  ) {
    rawClients = clients
    rawProviders = providers
    DispatchQueue.main.async { [rawClients, rawProviders, weak self] in
      self?.mutate { d in
        if rawClients[d.selectedClientKey] == nil {
          d.selectedClientKey = rawClients.keys.sorted().first ?? ""
        }
        if rawProviders[d.selectedProviderKey] == nil {
          d.selectedProviderKey = rawProviders.keys.sorted().first ?? ""
        }
      }
    }
  }

  // MARK: - Build invoice (pure)
  func build() -> Invoice {
    let d = draft
    let clientRaw = rawClients[d.selectedClientKey]!
    let providerRaw = rawProviders[d.selectedProviderKey]!
    debugPublish("InvoiceBuilder", "build invoked")
    let langKey = d.language == "ro" ? "ro" : "en"
    let clientMap = clientRawValue(clientRaw, langKey) ?? [:]
    let providerMap = providerRawValue(providerRaw, langKey) ?? [:]
    let clientOrder = InvoiceDataLoader.shared.orderedClientKeys(
      client: d.selectedClientKey, lang: langKey)
    let providerOrder = InvoiceDataLoader.shared.orderedProviderKeys(
      provider: d.selectedProviderKey, lang: langKey)
    func ordered(_ dict: [String: String], order: [String]) -> [Party.FieldLine] {
      let keys = order.isEmpty ? Array(dict.keys) : order
      return keys.compactMap { k in
        guard let v = dict[k] else { return nil }
        return Party.FieldLine(
          key: k, value: v,
          isBold: k.hasSuffix("-B") || k.localizedCaseInsensitiveContains("Role-B")
            || k.localizedCaseInsensitiveContains("Rol-B"))
      }
    }
    let clientFields = clientMap.merging(["Currency": clientRaw.curr]) { $1 }
    let providerFields = providerMap.merging(["Currency": providerRaw.curr]) { $1 }
    let clientParty = Party(
      name: d.selectedClientKey, fields: clientFields,
      ordered: ordered(clientFields, order: clientOrder))
    let providerParty = Party(
      name: d.selectedProviderKey, fields: providerFields,
      ordered: ordered(providerFields, order: providerOrder))

    let paymentLines: [Party.FieldLine]? = {
      guard let pay = providerRaw.payment else { return nil }
      let map = (d.language == "ro" ? pay["ro"] : pay["en"]) ?? pay["en"] ?? pay["ro"]
      guard let pmap = map else { return nil }
      let payOrder = InvoiceDataLoader.shared.orderedPaymentKeys(
        provider: d.selectedProviderKey, lang: langKey)
      let keys = payOrder.isEmpty ? Array(pmap.keys) : payOrder
      return keys.compactMap { k in
        pmap[k].map { Party.FieldLine(key: k, value: $0, isBold: k.hasSuffix("-B")) }
      }
    }()

    func findValue(_ map: [String: String], contains any: [String]) -> String? {
      map.first { k, _ in any.contains { k.localizedCaseInsensitiveContains($0) } }?.value
    }
    let itemMap = (clientRaw.item[langKey] ?? clientRaw.item["en"] ?? [:])
    let descValue =
      findValue(itemMap, contains: ["Descriere", "Description"]) ?? findValue(
        itemMap, contains: ["Description"]) ?? ""
    let priceString = findValue(itemMap, contains: ["Preț Unitar", "Preț", "Price"]) ?? "0 USD"
    let unitValue = findValue(itemMap, contains: ["Unitate", "Unit"]) ?? "unit"
    let quantityToken = findValue(itemMap, contains: ["Cantitate", "Quantity"]) ?? "-"
    let parsed = parsePrice(priceString)

    let primaryQty: Double = {
      if quantityToken.trimmingCharacters(in: .whitespacesAndNewlines) == "-" { return d.quantity }
      return Double(quantityToken) ?? d.quantity
    }()

    var items: [ItemLine] = [
      ItemLine(
        description: descValue.isEmpty ? "Services" : descValue,
        unitPrice: Money(amount: parsed.amount, currency: parsed.currency),
        unit: unitValue, quantity: primaryQty, isBonus: false)
    ]

    if d.includeBonus, let bMap = (clientRaw.bonus?[langKey] ?? clientRaw.bonus?["en"]) {
      let bDesc = findValue(bMap, contains: ["Descriere", "Description"]) ?? "Bonus"
      let bPriceString = findValue(bMap, contains: ["Preț Unitar", "Price"]) ?? "0 USD"
      let bUnit = findValue(bMap, contains: ["Unitate", "Unit"]) ?? "unit"
      let bQtyToken = findValue(bMap, contains: ["Cantitate", "Quantity"]) ?? "1"
      let bParsed = parsePrice(bPriceString)
      let bQty = Double(bQtyToken.trimmingCharacters(in: .whitespacesAndNewlines)) ?? 1
      items.append(
        ItemLine(
          description: bDesc,
          unitPrice: Money(amount: bParsed.amount, currency: bParsed.currency),
          unit: bUnit, quantity: bQty, isBonus: true))
    }

    let exRate: Double? = d.useExchange ? Double(d.customExchangeRate) ?? 5.9 : nil

    var invoice = Invoice(
      series: d.invoiceSeries, number: d.invoiceNo, issueDate: d.issueDate, dueDate: d.dueDate,
      client: clientParty, provider: providerParty, currencySource: parsed.currency,
      currencyTarget: providerRaw.curr, exchangeRate: exRate, items: items, language: d.language,
      paymentLines: paymentLines)
    if let override = Double(d.customTotal), override > 0, exRate != nil {
      let neededRate = override / invoice.totalSource
      invoice = Invoice(
        series: d.invoiceSeries, number: d.invoiceNo, issueDate: d.issueDate, dueDate: d.dueDate,
        client: clientParty, provider: providerParty, currencySource: parsed.currency,
        currencyTarget: providerRaw.curr, exchangeRate: neededRate, items: items,
        language: d.language, paymentLines: paymentLines)
    }
    return invoice
  }

  // Returns a cached invoice if draft unchanged, otherwise rebuilds and caches.
  func cachedInvoice() -> Invoice {
    if let snap = cachedDraftSnapshot, snap == draft, let inv = cachedInvoiceValue { return inv }
    let inv = build()
    cachedDraftSnapshot = draft
    cachedInvoiceValue = inv
    return inv
  }

  // MARK: - Validation
  var quantityValid: Bool { draft.quantity > 0 }
  var exchangeRateValid: Bool {
    !draft.useExchange || draft.customExchangeRate.isEmpty
      || Double(draft.customExchangeRate) != nil
  }
  var overrideTotalValid: Bool { draft.customTotal.isEmpty || Double(draft.customTotal) != nil }
  var isValid: Bool { quantityValid && exchangeRateValid && overrideTotalValid }

  // MARK: - Persistence
  private func restore() {
    guard let data = UserDefaults.standard.data(forKey: defaultsKey),
      let saved = try? JSONDecoder().decode(SavedState.self, from: data)
    else { return }
    mutate { d in
      d.invoiceSeries = saved.invoiceSeries
      d.invoiceNo = saved.invoiceNo
      d.issueDate = saved.issueDate
      d.dueDate = saved.dueDate
      d.language = saved.language
      d.quantity = saved.quantity
      d.selectedClientKey = saved.client
      d.selectedProviderKey = saved.provider
      d.useExchange = saved.useExchange
      d.customExchangeRate = saved.customExchangeRate
      d.customTotal = saved.customTotal
      d.includeBonus = saved.includeBonus
    }
  }

  func persist() {
    let d = draft
    let state = SavedState(
      invoiceSeries: d.invoiceSeries, invoiceNo: d.invoiceNo, issueDate: d.issueDate,
      dueDate: d.dueDate,
      language: d.language, quantity: d.quantity, client: d.selectedClientKey,
      provider: d.selectedProviderKey, useExchange: d.useExchange,
      customExchangeRate: d.customExchangeRate, customTotal: d.customTotal,
      includeBonus: d.includeBonus)
    if let data = try? JSONEncoder().encode(state) {
      UserDefaults.standard.set(data, forKey: defaultsKey)
    }
  }

  struct SavedState: Codable {
    let invoiceSeries: String
    let invoiceNo: String
    let issueDate: Date
    let dueDate: Date
    let language: String
    let quantity: Double
    let client: String
    let provider: String
    let useExchange: Bool
    let customExchangeRate: String
    let customTotal: String
    let includeBonus: Bool
  }

  // MARK: - Exchange rate fetch
  func fetchExchangeRate() async {
    guard draft.useExchange else { return }
    mutate { $0.fetchingRate = true }
    do {
      let d = draft
      let clientRaw = rawClients[d.selectedClientKey]!
      let providerRaw = rawProviders[d.selectedProviderKey]!
      let fromCurrency =
        (parsePrice(
          (clientRaw.item[d.language] ?? clientRaw.item["en"])?.first {
            $0.key.localizedCaseInsensitiveContains("Price")
              || $0.key.localizedCaseInsensitiveContains("Unitar")
          }?.value ?? "0 USD"
        ).currency)
      let toCurrency = providerRaw.curr
      let rate = try await ExchangeRateService.shared.fetchRate(from: fromCurrency, to: toCurrency)
      await MainActor.run { self.mutate { $0.customExchangeRate = String(format: "%.2f", rate) } }
    } catch {
      await MainActor.run {
        self.mutate {
          $0.errorMessage = (error as? LocalizedError)?.errorDescription ?? "Rate fetch failed"
        }
      }
    }
    await MainActor.run { self.mutate { $0.fetchingRate = false } }
  }

  private func clientRawValue(_ c: InvoiceDataLoader.RawClient, _ lang: String) -> [String: String]?
  {
    (lang == "ro" ? c.ro : c.en) ?? c.en ?? c.ro
  }
  private func providerRawValue(_ p: InvoiceDataLoader.RawProvider, _ lang: String) -> [String:
    String]?
  {
    (lang == "ro" ? p.ro : p.en) ?? p.en ?? p.ro
  }

  private func parsePrice(_ s: String) -> (amount: Double, currency: String) {
    let parts = s.split(separator: " ")
    if parts.count >= 2, let a = Double(parts[0]) { return (a, String(parts[1])) }
    return (0, "USD")
  }

  // MARK: - SwiftUI binding convenience
  func binding<T>(_ keyPath: WritableKeyPath<Draft, T>) -> Binding<T> {
    Binding(
      get: { self.draft[keyPath: keyPath] },
      set: { newValue in
        self.mutate { $0[keyPath: keyPath] = newValue }
      })
  }
}
