import Foundation

// Basic domain models mirroring the Python JSON structures
struct Party: Codable, Identifiable {
  var id: String { name }
  let name: String
  let fields: [String: String]  // existing map (may be used for lookups)
  let ordered: [FieldLine]
  struct FieldLine: Codable {
    let key: String
    let value: String
    let isBold: Bool
  }
}

struct PaymentDetails: Codable {
  let lines: [String: String]
}

struct ItemLine: Codable, Identifiable {
  var id: String { description }
  let description: String
  let unitPrice: Money
  let unit: String
  let quantity: Double
  let isBonus: Bool
}

struct Money: Codable, Hashable {
  let amount: Double
  let currency: String
}

struct Invoice: Identifiable, Codable {
  var id: String { series + number }
  let series: String
  let number: String
  let issueDate: Date
  let dueDate: Date
  let client: Party
  let provider: Party
  let currencySource: String
  let currencyTarget: String
  let exchangeRate: Double?  // nil when not applied
  let items: [ItemLine]
  let language: String?
  let paymentLines: [Party.FieldLine]?  // ordered payment lines for provider

  var totalSource: Double { items.reduce(0) { $0 + $1.unitPrice.amount * $1.quantity } }
  var totalTarget: Double? {
    guard let r = exchangeRate else { return nil }
    return (totalSource * r).rounded(to: 2)
  }
}

extension Double {
  func rounded(to places: Int) -> Double {
    let p = pow(10.0, Double(places))
    return (self * p).rounded() / p
  }
}

extension Party.FieldLine: Equatable {}
extension Party: Equatable {
  static func == (lhs: Party, rhs: Party) -> Bool {
    lhs.name == rhs.name && lhs.ordered == rhs.ordered
  }
}
extension ItemLine: Equatable {}
extension Invoice: Equatable {
  static func == (lhs: Invoice, rhs: Invoice) -> Bool {
    lhs.series == rhs.series && lhs.number == rhs.number && lhs.issueDate == rhs.issueDate
      && lhs.dueDate == rhs.dueDate && lhs.client == rhs.client && lhs.provider == rhs.provider
      && lhs.currencySource == rhs.currencySource && lhs.currencyTarget == rhs.currencyTarget
      && lhs.exchangeRate == rhs.exchangeRate && lhs.items == rhs.items
      && lhs.language == rhs.language
      && lhs.paymentLines?.map { $0.value } == rhs.paymentLines?.map { $0.value }
  }
}
