# InvoiceApp (SwiftUI macOS Prototype)

A modern SwiftUI prototype of the existing Python invoice generator. High-performance native UI, structured models, and room for future PDF and API integrations.

## Current Features
- Native macOS SwiftUI app scaffold (macOS 13+)
- Data models for Parties, Items, Invoice, Money
- Sample in-memory invoice with provider & client sections
- Items grid with computed totals
- Exchange rate section placeholder
- Modern UI elements (NavigationSplitView, material backgrounds)

## Planned / Next Steps
1. Import existing JSON (`clients.json`, `provider.json`) into Resources and build a loader mapping localized keys
2. Add dynamic form to create new invoice (series, number, dates, quantity, client/provider pickers)
3. Implement exchange rate fetch (use `URLSession` hitting existing API endpoint)
4. PDF export using PDFKit replicating current layout
5. Settings screen for API key storage in Keychain
6. Multi-language UI (Romanian / English toggle)
7. Bonus line toggling & validation
8. Currency formatting via `NumberFormatter` respecting locale

### Local Application Bundle & Install (No Signing)

You can build a self-contained `.app` bundle and copy it into your user `Applications` folder.

Prerequisites: Xcode command line tools (for `swift`).

Steps:
1. Build & assemble the app bundle:
	`make app`
2. Install to `~/Applications`:
	`make install`
3. Launch:
	Open Finder -> `~/Applications/InvoiceApp.app` (or run `open ~/Applications/InvoiceApp.app`).

The bundle gets created at `dist/InvoiceApp.app` with:
```
Contents/
  Info.plist
  MacOS/InvoiceApp (binary)
  Resources/AppIcon.icns (optional if provided)
```

### Adding a Custom Icon
Provide an `AppIcon.icns` file at `Packaging/AppIcon.icns` before running `make app`.

Quick way to create an `.icns` from a PNG (1024x1024 recommended):
```
mkdir Icon.iconset
sips -z 16 16     icon.png --out Icon.iconset/icon_16x16.png
sips -z 32 32     icon.png --out Icon.iconset/icon_16x16@2x.png
sips -z 32 32     icon.png --out Icon.iconset/icon_32x32.png
sips -z 64 64     icon.png --out Icon.iconset/icon_32x32@2x.png
sips -z 128 128   icon.png --out Icon.iconset/icon_128x128.png
sips -z 256 256   icon.png --out Icon.iconset/icon_128x128@2x.png
sips -z 256 256   icon.png --out Icon.iconset/icon_256x256.png
sips -z 512 512   icon.png --out Icon.iconset/icon_256x256@2x.png
sips -z 512 512   icon.png --out Icon.iconset/icon_512x512.png
cp icon.png Icon.iconset/icon_512x512@2x.png
iconutil -c icns Icon.iconset -o Packaging/AppIcon.icns
rm -rf Icon.iconset
```
Rebuild with `make app`.

If starting from the provided vector `Packaging/AppIcon.svg`, first export a 1024x1024 PNG (using Preview, Inkscape, or `rsvg-convert`), then follow the steps above.

### Updating the Version
Edit `Packaging/Info.plist` keys `CFBundleShortVersionString` and `CFBundleVersion`.

### Uninstall
Remove the installed bundle:
`rm -rf ~/Applications/InvoiceApp.app`

## Building
Requires Xcode 15 / Swift 5.9+.

```
xcodebuild -scheme InvoiceApp
```
Or open the package in Xcode: `File > Open` and select the `invoice-mac-app` folder.

## Architecture
- Swift Package with an executable target
- `Models.swift` defines core immutable models
- `InvoiceDataLoader` provides a sample invoice (to be replaced with JSON-driven implementation)
- `Main.swift` defines the SwiftUI App & root `ContentView`

## JSON Mapping Plan
Map Python JSON -> Swift structs:
- Normalize bilingual keys by storing per-locale dictionaries
- Provide a `LocalizationService` to pick current language
- Convert price strings like `"23 GBP"` into `Money(amount: 23, currency: "GBP")`

## PDF Export Plan
1. Use PDFKit (`PDFPage` drawing via CoreGraphics) or `Render` a SwiftUI view with `GraphicsContext` (macOS 14+ API) for advanced layout.
2. Mirror existing layout sections: header, parties blocks, items table, totals, payment details.
3. Reuse formatting helpers; measure text for wrapping (similar to current `textwrap`).

## License
Internal prototype draft. Add license before distribution.
