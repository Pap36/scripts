import Foundation
import SwiftUI

struct LayoutConfig: Codable, Equatable {
  var pageWidth: CGFloat = 595
  var pageHeight: CGFloat = 842
  var marginLeft: CGFloat = 50
  var marginRight: CGFloat = 550
  var topStartY: CGFloat = 780
  var lineHeight: CGFloat = 12
  var sectionSpacing: CGFloat = 8
  var wrapWidth: Int = 25
  var descColumnX: CGFloat = 50
  var priceColumnX: CGFloat = 280
  var unitColumnX: CGFloat = 360
  var qtyColumnX: CGFloat = 550
  var headerFontSize: CGFloat = 12
  var bodyFontSize: CGFloat = 8
  var boldHeaderFontSize: CGFloat = 12
  var showSectionRules: Bool = true
}

@MainActor
final class LayoutSettings: ObservableObject {
  @Published var config: LayoutConfig { didSet { persist() } }
  private let defaultsKey = "InvoiceLayoutSettingsV1"
  init() { self.config = Self.restore() }
  private static func restore() -> LayoutConfig {
    if let data = UserDefaults.standard.data(forKey: "InvoiceLayoutSettingsV1"),
      let cfg = try? JSONDecoder().decode(LayoutConfig.self, from: data)
    {
      return cfg
    }
    return LayoutConfig()
  }
  private func persist() {
    if let data = try? JSONEncoder().encode(config) {
      UserDefaults.standard.set(data, forKey: defaultsKey)
    }
  }
}
