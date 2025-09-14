import AppKit  // Needed for NSApplication activation
import Foundation
import PDFKit
import SwiftUI

// Simple helper to read version/build from Info.plist
enum AppVersion {
  static var short: String {
    Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0"
  }
  static var build: String {
    Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "1"
  }
  static var formatted: String { "v" + short + " (" + build + ")" }
}

// AppDelegate to force activation so the app shows in Cmd+Tab and brings its window forward.
final class AppDelegate: NSObject, NSApplicationDelegate {
  func applicationDidFinishLaunching(_ notification: Notification) {
    // Ensure app is a regular app with dock icon & appears in Cmd+Tab.
    NSApplication.shared.setActivationPolicy(.regular)
    // Activate on next runloop tick to avoid racing window creation.
    DispatchQueue.main.async {
      NSApplication.shared.activate(ignoringOtherApps: true)
    }
  }
}

@main
struct InvoiceMainApp: App {
  @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
  @StateObject private var builder = InvoiceBuilder()
  @StateObject private var layoutSettings = LayoutSettings()
  @StateObject private var resourceStore = ResourceStore()
  // Removed global invoice state; invoice now derived on demand from builder

  init() {
    DispatchQueue.main.async {
      NSApplication.shared.setActivationPolicy(.regular)
      NSApplication.shared.activate(ignoringOtherApps: true)
    }
  }

  var body: some Scene {
    WindowGroup("Invoice Generator") {
      TabView {
        ContentView(builder: builder, layout: layoutSettings)
          .tabItem { Text("Editor") }
        LayoutSettingsView(settings: layoutSettings, builder: builder)
          .tabItem { Text("Settings") }
        ResourcesView(store: resourceStore) { c, p in
          DispatchQueue.main.async { builder.applyData(clients: c, providers: p) }
        }
        .tabItem { Text("Resources") }
      }
      .frame(minWidth: 1250, minHeight: 760)
    }
  }
}

struct ContentView: View {
  @ObservedObject var builder: InvoiceBuilder
  @ObservedObject var layout: LayoutSettings
  @State private var showExchange: Bool = true
  @State private var autoUpdate: Bool = true
  @State private var rebuildWork: DispatchWorkItem? = nil

  var body: some View {
    NavigationSplitView(
      sidebar: { sidebarContent },
      detail: {
        ScrollView {
          VStack(alignment: .leading, spacing: 24) {
            parties
            itemsTable
            if showExchange, let rate = builder.cachedInvoice().exchangeRate {
              exchangeRateView(rate)
            }
            exportButtons
            Divider().padding(.top, 8)
            Text("InvoiceApp " + AppVersion.formatted)
              .font(.caption2)
              .foregroundColor(.secondary)
              .frame(maxWidth: .infinity, alignment: .center)
              .padding(.bottom, 8)
          }
          .padding(24)
        }
      }
    )
    // No invoice state mutation; view reads derived data directly.
  }

  private var parties: some View {
    HStack(alignment: .top, spacing: 40) {
      let inv = builder.cachedInvoice()
      partyBox(title: "Provider", fields: inv.provider.fields)
      partyBox(title: "Client", fields: inv.client.fields)
      Spacer()
    }
  }

  private func partyBox(title: String, fields: [String: String]) -> some View {
    VStack(alignment: .leading, spacing: 8) {
      Text(title).font(.headline)
      // Use the key string itself as the stable identity. The previous version used the literal string ".self" which is incorrect.
      ForEach(Array(fields.keys).sorted(), id: \.self) { key in
        let value = fields[key] ?? ""
        if key.hasSuffix("-B") { Text(value).fontWeight(.bold) } else { Text(value) }
      }
    }
    .padding(12)
    .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
  }

  private var itemsTable: some View {
    VStack(alignment: .leading) {
      Text("Items").font(.headline)
      Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 6) {
        GridRow {
          header("Description")
          header("Unit Price")
          header("Qty")
          header("Line Total")
        }
        Divider()
        ForEach(builder.cachedInvoice().items) { line in
          GridRow {
            Text(line.description)
            Text(money(line.unitPrice.amount, line.unitPrice.currency))
            Text(String(format: "%.2f", line.quantity))
            Text(money(line.unitPrice.amount * line.quantity, line.unitPrice.currency))
          }
          if line.isBonus {
            GridRow {
              Text("Bonus").foregroundColor(.orange)
              Text("")
              Text("")
              Text("Included").foregroundColor(.orange)
            }
          }
        }
      }
    }
  }

  private func header(_ t: String) -> some View {
    Text(t).font(.caption).foregroundStyle(.secondary)
  }

  private func exchangeRateView(_ rate: Double) -> some View {
    VStack(alignment: .leading, spacing: 4) {
      let inv = builder.cachedInvoice()
      Text("Exchange Rate").font(.headline)
      Text("1 \(inv.currencySource) = \(String(format: "%.2f", rate)) \(inv.currencyTarget)")
      if let total = inv.totalTarget {
        Text("Converted total: \(money(total, inv.currencyTarget))").font(.subheadline)
      }
    }
    .padding(12)
    .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
  }

  private var exportButtons: some View {
    HStack {
      Button("Export PDF") {
        PDFExporter.export(invoice: builder.cachedInvoice(), config: layout.config)
      }
      .buttonStyle(.borderedProminent)
      Button(showExchange ? "Hide FX" : "Show FX") { withAnimation { showExchange.toggle() } }
      Toggle("Auto Update", isOn: $autoUpdate).toggleStyle(.switch)
      Button("Update Now") { builder.persist() }
      Spacer()
    }
  }

  // Formatting helpers
  private func money(_ amount: Double, _ currency: String) -> String {
    "\(String(format: "%.2f", amount)) \(currency)"
  }
  private func format(_ date: Date) -> String {
    let f = DateFormatter()
    f.dateFormat = "dd/MM/yyyy"
    return f.string(from: date)
  }
}

// MARK: - Sidebar editable content
extension ContentView {
  private var sidebarContent: some View {
    List {
      Section("Editable Parameters") {
        TextField("Series", text: builder.binding(\.invoiceSeries))
        TextField("Number", text: builder.binding(\.invoiceNo))
        DatePicker("Issue", selection: builder.binding(\.issueDate), displayedComponents: .date)
        DatePicker("Due", selection: builder.binding(\.dueDate), displayedComponents: .date)
        Picker("Language", selection: builder.binding(\.language)) {
          Text("EN").tag("en")
          Text("RO").tag("ro")
        }
        Picker("Client", selection: builder.binding(\.selectedClientKey)) {
          ForEach(builder.rawClients.keys.sorted(), id: \.self) { Text($0) }
        }
        Picker("Provider", selection: builder.binding(\.selectedProviderKey)) {
          ForEach(builder.rawProviders.keys.sorted(), id: \.self) { Text($0) }
        }
        HStack {
          Text("Quantity")
          Spacer()
          TextField("Qty", value: builder.binding(\.quantity), format: .number)
            .frame(width: 70)
        }
        Toggle("Bonus", isOn: builder.binding(\.includeBonus))
        Toggle("Use FX", isOn: builder.binding(\.useExchange))
        TextField("FX Rate", text: builder.binding(\.customExchangeRate))
        TextField("Override Total", text: builder.binding(\.customTotal))
        if builder.draft.fetchingRate { ProgressView().controlSize(.small) }
        Button("Fetch Rate") {
          Task {
            await builder.fetchExchangeRate()
          }
        }
        .disabled(!builder.draft.useExchange || builder.draft.fetchingRate)
        if let err = builder.draft.errorMessage { Text(err).font(.caption).foregroundColor(.red) }
        if !builder.quantityValid {
          Text("Quantity must be > 0").font(.caption).foregroundColor(.red)
        }
        if !builder.exchangeRateValid {
          Text("FX rate must be numeric").font(.caption).foregroundColor(.red)
        }
        if !builder.overrideTotalValid {
          Text("Override total must be numeric").font(.caption).foregroundColor(.red)
        }
      }
      Section("Computed Totals") {
        let inv = builder.cachedInvoice()
        LabeledContent("Source", value: money(inv.totalSource, inv.currencySource))
        if let t = inv.totalTarget {
          LabeledContent("Target", value: money(t, inv.currencyTarget))
        }
      }
    }
    .listStyle(.sidebar)
  }

  // Rebuild helper removed; invoice derived directly.
}

struct LayoutSettingsView: View {
  @ObservedObject var settings: LayoutSettings
  @ObservedObject var builder: InvoiceBuilder
  @State private var pdfData: Data = Data()
  @State private var debounceWork: DispatchWorkItem?
  var body: some View {
    HStack(alignment: .top, spacing: 24) {
      PDFKitRepresentedView(data: pdfData)
        .frame(minWidth: 620, maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(NSColor.controlBackgroundColor))
        .overlay(RoundedRectangle(cornerRadius: 4).stroke(Color.gray.opacity(0.25)))
      ScrollView {
        VStack(alignment: .leading, spacing: 18) {
          Text("Layout Settings").font(.title3).padding(.bottom, 4)
          groupBox("Page") {
            StepperRow(label: "Width", value: $settings.config.pageWidth, range: 400...900, step: 1)
            StepperRow(
              label: "Height", value: $settings.config.pageHeight, range: 600...1200, step: 1)
          }
          groupBox("Margins & Columns") {
            SliderRow(label: "Left", value: $settings.config.marginLeft, range: 20...150)
            SliderRow(label: "Right", value: $settings.config.marginRight, range: 400...580)
            Divider()
            SliderRow(label: "Desc X", value: $settings.config.descColumnX, range: 40...200)
            SliderRow(label: "Price X", value: $settings.config.priceColumnX, range: 150...400)
            SliderRow(label: "Unit X", value: $settings.config.unitColumnX, range: 200...450)
            SliderRow(label: "Qty X", value: $settings.config.qtyColumnX, range: 450...600)
          }
          groupBox("Typography") {
            SliderRow(label: "Body Size", value: $settings.config.bodyFontSize, range: 6...16)
            SliderRow(label: "Header Size", value: $settings.config.headerFontSize, range: 8...22)
            SliderRow(
              label: "Bold Header", value: $settings.config.boldHeaderFontSize, range: 10...28)
            SliderRow(label: "Line Height", value: $settings.config.lineHeight, range: 8...28)
            Stepper(
              "Wrap Width: \(settings.config.wrapWidth)", value: $settings.config.wrapWidth,
              in: 15...80)
          }
          groupBox("Misc") {
            Toggle("Section Rules", isOn: $settings.config.showSectionRules)
            SliderRow(label: "Top Start Y", value: $settings.config.topStartY, range: 500...820)
            Button("Reset Defaults") { settings.config = LayoutConfig() }
              .buttonStyle(.bordered)
          }
          Spacer(minLength: 40)
        }
        .frame(width: 380)
        .padding(.vertical, 16)
        .padding(.horizontal, 12)
      }
      .background(Color(nsColor: .windowBackgroundColor))
    }
    .padding(16)
    .onAppear { refreshPreview() }
    .onChange(of: settings.config) { _ in debounceRefresh() }
    .onReceive(builder.objectWillChange) { _ in debounceRefresh() }
  }
  private func groupBox(_ title: String, @ViewBuilder content: () -> some View) -> some View {
    GroupBox(label: Text(title).font(.headline)) {
      VStack(alignment: .leading, spacing: 10) { content() }
    }
  }
  private func refreshPreview() {
    pdfData = PDFExporter.data(invoice: builder.cachedInvoice(), config: settings.config)
  }
  private func debounceRefresh() {
    debounceWork?.cancel()
    let work = DispatchWorkItem { refreshPreview() }
    debounceWork = work
    DispatchQueue.main.asyncAfter(deadline: .now() + 0.2, execute: work)
  }
}

struct SliderRow: View {
  var label: String
  @Binding var value: CGFloat
  var range: ClosedRange<CGFloat>
  var body: some View {
    HStack(spacing: 12) {
      Text(label).frame(width: 100, alignment: .leading)
      Slider(value: $value, in: range)
      Text(String(format: "%.0f", value)).monospacedDigit().frame(width: 44)
    }
  }
}

struct StepperRow: View {
  var label: String
  @Binding var value: CGFloat
  var range: ClosedRange<CGFloat>
  var step: CGFloat
  var body: some View {
    HStack {
      Text(label).frame(width: 100, alignment: .leading)
      Stepper(
        value: Binding(get: { Double(value) }, set: { value = CGFloat($0) }),
        in: Double(range.lowerBound)...Double(range.upperBound), step: Double(step)
      ) {
        Text(String(format: "%.0f", value)).monospacedDigit()
      }
    }
  }
}

// Separate PDFPreviewView removed; preview integrated inside Settings.

struct PDFKitRepresentedView: NSViewRepresentable {
  let data: Data
  func makeNSView(context: Context) -> PDFView {
    let v = PDFView()
    v.autoScales = true
    if let doc = PDFDocument(data: data) { v.document = doc }
    return v
  }
  func updateNSView(_ nsView: PDFView, context: Context) {
    if let doc = PDFDocument(data: data) { nsView.document = doc }
  }
}
