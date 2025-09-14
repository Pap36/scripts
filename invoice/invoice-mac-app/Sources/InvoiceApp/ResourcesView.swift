import SwiftUI

struct ResourcesView: View {
  @ObservedObject var store: ResourceStore
  var apply:
    (
      _ clients: [String: InvoiceDataLoader.RawClient],
      _ providers: [String: InvoiceDataLoader.RawProvider]
    ) -> Void
  @State private var newClientKey: String = ""
  @State private var newProviderKey: String = ""

  var body: some View {
    HStack(alignment: .top) {
      VStack(alignment: .leading) {
        Text("Clients").font(.headline)
        List(selection: Binding(get: { store.selectedClient }, set: { store.selectedClient = $0 }))
        {
          ForEach(store.clients.keys.sorted(), id: \.self) { key in
            Text(key)
              .tag(Optional(key))
          }
        }
        HStack {
          TextField("New client key", text: $newClientKey)
          Button("Add") {
            if !newClientKey.isEmpty {
              store.addClient(key: newClientKey)
              newClientKey = ""
            }
          }
        }
        if let key = store.selectedClient { clientEditor(key) }
      }
      Divider()
      VStack(alignment: .leading) {
        Text("Providers").font(.headline)
        List(
          selection: Binding(get: { store.selectedProvider }, set: { store.selectedProvider = $0 })
        ) {
          ForEach(store.providers.keys.sorted(), id: \.self) { key in
            Text(key)
              .tag(Optional(key))
          }
        }
        HStack {
          TextField("New provider key", text: $newProviderKey)
          Button("Add") {
            if !newProviderKey.isEmpty {
              store.addProvider(key: newProviderKey)
              newProviderKey = ""
            }
          }
        }
        if let key = store.selectedProvider { providerEditor(key) }
      }
      Spacer(minLength: 30)
      VStack(alignment: .leading, spacing: 12) {
        Button("Apply to Builder") { apply(store.clients, store.providers) }
          .buttonStyle(.borderedProminent)
        Button("Save Copies") { store.saveAll() }
        Button("Reload From Bundle") { store.refreshFromBundle() }
        Text(store.status).font(.caption).foregroundColor(.secondary).frame(
          maxWidth: 250, alignment: .leading)
        Spacer()
      }
    }
    .padding(16)
    .onChange(of: store.selectedClient) { newVal in
      DispatchQueue.main.async { store.handleClientSelectionChange(newVal) }
    }
    .onChange(of: store.selectedProvider) { newVal in
      DispatchQueue.main.async { store.handleProviderSelectionChange(newVal) }
    }
  }

  // Removed function kvEditor; replaced by KVEditor view below.

  private func clientEditor(_ key: String) -> some View {
    return ScrollView {
      VStack(alignment: .leading, spacing: 14) {
        Text("Edit Client: \(key)").font(.headline)
        HStack {
          Text("Currency")
          TextField("Curr", text: $store.editingClientCurr)
        }
        KVEditor(title: "RO", dict: $store.editingClientRO)
        KVEditor(title: "EN", dict: $store.editingClientEN)
        Divider()
        Text("Item Section").font(.subheadline.bold())
        KVEditor(title: "Item RO", dict: $store.editingClientItemRO)
        KVEditor(title: "Item EN", dict: $store.editingClientItemEN)
        Divider()
        Text("Bonus Section (Optional)").font(.subheadline.bold())
        KVEditor(title: "Bonus RO", dict: $store.editingClientBonusRO)
        KVEditor(title: "Bonus EN", dict: $store.editingClientBonusEN)
        Button("Commit Client Changes") { store.commitClientEdits() }
          .buttonStyle(.borderedProminent)
      }.frame(maxWidth: 360)
    }
  }
  private func providerEditor(_ key: String) -> some View {
    return ScrollView {
      VStack(alignment: .leading, spacing: 14) {
        Text("Edit Provider: \(key)").font(.headline)
        HStack {
          Text("Currency")
          TextField("Curr", text: $store.editingProviderCurr)
        }
        KVEditor(title: "RO", dict: $store.editingProviderRO)
        KVEditor(title: "EN", dict: $store.editingProviderEN)
        Divider()
        Text("Payment Section").font(.subheadline.bold())
        KVEditor(title: "Payment RO", dict: $store.editingProviderPaymentRO)
        KVEditor(title: "Payment EN", dict: $store.editingProviderPaymentEN)
        Divider()
        Text("Bonus Section (Optional)").font(.subheadline.bold())
        KVEditor(title: "Bonus RO", dict: $store.editingProviderBonusRO)
        KVEditor(title: "Bonus EN", dict: $store.editingProviderBonusEN)
        Button("Commit Provider Changes") { store.commitProviderEdits() }
          .buttonStyle(.borderedProminent)
      }.frame(maxWidth: 360)
    }
  }
}

// MARK: - KVEditor reusable component
private struct KVEditor: View {
  let title: String
  @Binding var dict: [String: String]
  @State private var newKey: String = ""
  @State private var newVal: String = ""
  @State private var error: String = ""

  var body: some View {
    VStack(alignment: .leading, spacing: 6) {
      HStack(alignment: .firstTextBaseline) {
        Text(title).font(.subheadline.bold())
        Spacer()
        Text("Add '-B' to key for bold").font(.caption2).foregroundColor(.secondary)
      }
      // Snapshot keys to avoid mutating collection while ForEach iterates
      let keys = dict.keys.sorted()
      ForEach(keys, id: \.self) { k in
        HStack(alignment: .center) {
          Text(k).frame(width: 140, alignment: .leading)
          TextField(
            "Value",
            text: Binding(
              get: { dict[k] ?? "" },
              set: { newVal in
                DispatchQueue.main.async { dict[k] = newVal }
                debugPublish("KVEditor", "change value for \(k) in \(title)")
              })
          )
          Button(role: .destructive) {
            DispatchQueue.main.async { dict.removeValue(forKey: k) }
            debugPublish("KVEditor", "remove key \(k) in \(title)")
          } label: {
            Image(systemName: "trash").foregroundColor(.red)
          }.buttonStyle(.plain)
        }
      }
      HStack {
        TextField("New key", text: $newKey)
          .textFieldStyle(.roundedBorder)
          .frame(width: 160)
        TextField("New value", text: $newVal)
          .textFieldStyle(.roundedBorder)
        Button("Add") {
          let trimmed = newKey.trimmingCharacters(in: .whitespacesAndNewlines)
          guard !trimmed.isEmpty else {
            error = "Key empty"
            return
          }
          guard dict[trimmed] == nil else {
            error = "Duplicate"
            return
          }
          DispatchQueue.main.async {
            dict[trimmed] = newVal
            debugPublish("KVEditor", "add key \(trimmed) in \(title)")
            newKey = ""
            newVal = ""
            error = ""
          }
        }.disabled(newKey.isEmpty)
      }
      if !error.isEmpty { Text(error).font(.caption2).foregroundColor(.red) }
    }
    .padding(8)
    .background(Color.gray.opacity(0.08), in: RoundedRectangle(cornerRadius: 6))
  }
}
