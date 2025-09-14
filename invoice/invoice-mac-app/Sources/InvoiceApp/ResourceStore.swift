import Foundation
import SwiftUI

// Uses RawClient / RawProvider types from InvoiceDataLoader

@MainActor
final class ResourceStore: ObservableObject {
  @Published var clients: [String: InvoiceDataLoader.RawClient]
  @Published var providers: [String: InvoiceDataLoader.RawProvider]
  @Published var selectedClient: String? = nil {
    didSet { debugPublish("ResourceStore", "selectedClient -> \(selectedClient ?? "nil")") }
  }
  @Published var selectedProvider: String? = nil {
    didSet { debugPublish("ResourceStore", "selectedProvider -> \(selectedProvider ?? "nil")") }
  }
  @Published var status: String = ""
  // Staging copies for editing (avoid mutating published dictionaries while SwiftUI traverses view)
  @Published var editingClientRO: [String: String] = [:]
  @Published var editingClientEN: [String: String] = [:]
  @Published var editingClientCurr: String = ""
  @Published var editingClientItemRO: [String: String] = [:]
  @Published var editingClientItemEN: [String: String] = [:]
  @Published var editingClientBonusRO: [String: String] = [:]
  @Published var editingClientBonusEN: [String: String] = [:]
  @Published var editingProviderRO: [String: String] = [:]
  @Published var editingProviderEN: [String: String] = [:]
  @Published var editingProviderCurr: String = ""
  @Published var editingProviderPaymentRO: [String: String] = [:]
  @Published var editingProviderPaymentEN: [String: String] = [:]
  @Published var editingProviderBonusRO: [String: String] = [:]
  @Published var editingProviderBonusEN: [String: String] = [:]

  init() {
    self.clients = InvoiceDataLoader.shared.loadClients()
    self.providers = InvoiceDataLoader.shared.loadProviders()
  }

  // Explicit selection handlers to be triggered from the View layer (.onChange) to avoid publishing during update cycles
  func handleClientSelectionChange(_ newValue: String?) {
    // Defer slightly so SwiftUI finishes processing the List selection mutation before we publish many field changes.
    DispatchQueue.main.asyncAfter(deadline: .now() + 0.01) { [weak self] in
      guard let self else { return }
      if let k = newValue { self.loadClientEditing(k) } else { self.clearClientEditing() }
      debugPublish("ResourceStore", "handleClientSelectionChange -> \(newValue ?? "nil") (delayed)")
    }
  }
  func handleProviderSelectionChange(_ newValue: String?) {
    DispatchQueue.main.asyncAfter(deadline: .now() + 0.01) { [weak self] in
      guard let self else { return }
      if let k = newValue { self.loadProviderEditing(k) } else { self.clearProviderEditing() }
      debugPublish(
        "ResourceStore", "handleProviderSelectionChange -> \(newValue ?? "nil") (delayed)")
    }
  }

  // Default templates for new entries (include commonly required keys so user just fills values)
  private func defaultClientRaw() -> InvoiceDataLoader.RawClient {
    let baseRO: [String: String] = [
      "Rol-B": "Client:",
      "Client": "",
      "Adresă": "",
      "Oraș": "",
      "Țară": "",
      "Cod Poștal": "",
    ]
    let baseEN: [String: String] = [
      "Role-B": "Client:",
      "Client": "",
      "Address": "",
      "City": "",
      "Country": "",
      "Postal code": "",
    ]
    // Minimal item section: description, unit price, unit, quantity placeholder '-'
    let itemRO: [String: String] = [
      "Descriere": "Descriere serviciu",
      "Preț Unitar": "0 USD",
      "Unitate": "1 oră",
      "Cantitate": "-",
    ]
    let itemEN: [String: String] = [
      "Description": "Service description",
      "Preț Unitar (Price)": "0 USD",
      "Unit": "1 hour",
      "Quantity": "-",
    ]
    let bonusRO: [String: String] = [
      // Provide optional sample structure commented out values the user can fill
      "Descriere": "Bonus serviciu",
      "Preț Unitar": "0 USD",
      "Unitate": "1 oră",
      "Cantitate": "1",
    ]
    let bonusEN: [String: String] = [
      "Description": "Service bonus",
      "Unit Price": "0 USD",
      "Unit": "1 hour",
      "Quantity": "1",
    ]
    return InvoiceDataLoader.RawClient(
      ro: baseRO, en: baseEN, curr: "USD", item: ["ro": itemRO, "en": itemEN],
      bonus: ["ro": bonusRO, "en": bonusEN])
  }
  private func defaultProviderRaw() -> InvoiceDataLoader.RawProvider {
    let baseRO: [String: String] = [
      "Rol-B": "Furnizor:",
      "Furnizor": "",
      "Adresă": "",
      "Oraș": "",
      "Țară": "",
      "Cod poștal": "",
      "CUI": "",
      "EUID": "",
    ]
    let baseEN: [String: String] = [
      "Role-B": "Furnizor (Provider):",
      "Provider": "",
      "Address": "",
      "City": "",
      "Country": "",
      "Zip": "",
      "CUI": "",
      "EUID": "",
    ]
    let payRO: [String: String] = [
      "Date plată-B": "Informații privind plata:",
      "Banca": "",
      "Adresă": "",
      "Titular Cont": "",
      "Numar de cont": "",
      "Cod": "",
    ]
    let payEN: [String: String] = [
      "Payment Information-B": "Informații privind plata (Payment information):",
      "Bank": "",
      "Address": "",
      "Account Holder": "",
      "Account Number": "",
      "Sort Code": "",
    ]
    let bonusRO: [String: String] = [
      "Descriere": "Bonus furnizor",
      "Preț Unitar": "0 USD",
      "Unitate": "1 oră",
      "Cantitate": "1",
    ]
    let bonusEN: [String: String] = [
      "Description": "Provider bonus",
      "Unit Price": "0 USD",
      "Unit": "1 hour",
      "Quantity": "1",
    ]
    return InvoiceDataLoader.RawProvider(
      ro: baseRO, en: baseEN, curr: "USD", payment: ["ro": payRO, "en": payEN],
      bonus: ["ro": bonusRO, "en": bonusEN])
  }

  func refreshFromBundle() {
    clients = InvoiceDataLoader.shared.loadClients()
    providers = InvoiceDataLoader.shared.loadProviders()
  }

  func addClient(key: String) {
    guard clients[key] == nil else {
      status = "Client exists"
      return
    }
    let tmpl = defaultClientRaw()
    clients[key] = tmpl
    selectedClient = key  // onChange will trigger load
    status = "Added client \(key)"
    debugPublish("ResourceStore", "addClient \(key)")
  }
  func addProvider(key: String) {
    guard providers[key] == nil else {
      status = "Provider exists"
      return
    }
    let tmpl = defaultProviderRaw()
    providers[key] = tmpl
    selectedProvider = key  // onChange will trigger load
    status = "Added provider \(key)"
    debugPublish("ResourceStore", "addProvider \(key)")
  }

  func loadClientEditing(_ key: String) {
    guard let c = clients[key] else { return }
    editingClientRO = c.ro ?? [:]
    editingClientEN = c.en ?? [:]
    editingClientCurr = c.curr
    editingClientItemRO = c.item["ro"] ?? [:]
    editingClientItemEN = c.item["en"] ?? [:]
    editingClientBonusRO = c.bonus?["ro"] ?? [:]
    editingClientBonusEN = c.bonus?["en"] ?? [:]
    debugPublish("ResourceStore", "loadClientEditing \(key)")
  }
  private func clearClientEditing() {
    editingClientRO = [:]
    editingClientEN = [:]
    editingClientCurr = ""
    editingClientItemRO = [:]
    editingClientItemEN = [:]
    editingClientBonusRO = [:]
    editingClientBonusEN = [:]
  }
  func loadProviderEditing(_ key: String) {
    guard let p = providers[key] else { return }
    editingProviderRO = p.ro ?? [:]
    editingProviderEN = p.en ?? [:]
    editingProviderCurr = p.curr
    editingProviderPaymentRO = p.payment?["ro"] ?? [:]
    editingProviderPaymentEN = p.payment?["en"] ?? [:]
    editingProviderBonusRO = p.bonus?["ro"] ?? [:]
    editingProviderBonusEN = p.bonus?["en"] ?? [:]
    debugPublish("ResourceStore", "loadProviderEditing \(key)")
  }
  private func clearProviderEditing() {
    editingProviderRO = [:]
    editingProviderEN = [:]
    editingProviderCurr = ""
    editingProviderPaymentRO = [:]
    editingProviderPaymentEN = [:]
    editingProviderBonusRO = [:]
    editingProviderBonusEN = [:]
  }

  func commitClientEdits() {
    guard let key = selectedClient, var existing = clients[key] else { return }
    var newItem = existing.item
    newItem["ro"] = editingClientItemRO
    newItem["en"] = editingClientItemEN
    var newBonus = existing.bonus ?? [:]
    if !editingClientBonusRO.isEmpty || !editingClientBonusEN.isEmpty {
      newBonus["ro"] = editingClientBonusRO.isEmpty ? nil : editingClientBonusRO
      newBonus["en"] = editingClientBonusEN.isEmpty ? nil : editingClientBonusEN
      // Remove empty language maps to keep JSON lean
      if newBonus["ro"] == nil && newBonus["en"] == nil { newBonus.removeAll() }
    }
    existing = InvoiceDataLoader.RawClient(
      ro: editingClientRO, en: editingClientEN, curr: editingClientCurr, item: newItem,
      bonus: newBonus.isEmpty ? nil : newBonus)
    clients[key] = existing
    status = "Client saved"
    debugPublish("ResourceStore", "commitClientEdits \(key)")
  }
  func commitProviderEdits() {
    guard let key = selectedProvider, var existing = providers[key] else { return }
    var newPayment = existing.payment ?? [:]
    newPayment["ro"] = editingProviderPaymentRO
    newPayment["en"] = editingProviderPaymentEN
    existing = InvoiceDataLoader.RawProvider(
      ro: editingProviderRO, en: editingProviderEN, curr: editingProviderCurr,
      payment: newPayment,
      bonus: {
        var b = existing.bonus ?? [:]
        if !editingProviderBonusRO.isEmpty || !editingProviderBonusEN.isEmpty {
          b["ro"] = editingProviderBonusRO.isEmpty ? nil : editingProviderBonusRO
          b["en"] = editingProviderBonusEN.isEmpty ? nil : editingProviderBonusEN
          if b["ro"] == nil && b["en"] == nil { b.removeAll() }
        }
        return b.isEmpty ? nil : b
      }())
    providers[key] = existing
    status = "Provider saved"
    debugPublish("ResourceStore", "commitProviderEdits \(key)")
  }

  // Persist edited JSON to user's Documents folder (does not overwrite bundle)
  private func saveJSON<T: Encodable>(_ value: T, name: String) throws -> URL {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
    let data = try encoder.encode(value)
    let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
    let url = dir.appendingPathComponent("invoice_\(name).json")
    try data.write(to: url)
    return url
  }
  func saveAll() {
    do {
      let cURL = try saveJSON(clients, name: "clients")
      let pURL = try saveJSON(providers, name: "providers")
      status = "Saved copies to: \n\(cURL.lastPathComponent)\n\(pURL.lastPathComponent)"
    } catch { status = "Save failed: \(error.localizedDescription)" }
  }
}
