import AppKit
import CoreText
import Foundation

enum PDFExporter {
  static func export(invoice: Invoice, config: LayoutConfig = LayoutConfig()) {
    let panel = NSSavePanel()
    panel.allowedContentTypes = [.pdf]
    panel.nameFieldStringValue = "Invoice_\(invoice.series)_\(invoice.number).pdf"
    panel.begin { result in
      guard result == .OK, let url = panel.url else { return }
      let data = render(invoice: invoice, config: config)
      do {
        try data.write(to: url)
        DispatchQueue.main.async {
          inform(title: "Export Complete", message: "Saved to \(url.lastPathComponent)")
        }
      } catch {
        NSLog("PDF export failed: \(error)")
        DispatchQueue.main.async {
          inform(title: "Export Failed", message: error.localizedDescription)
        }
      }
    }
  }
  static func data(invoice: Invoice, config: LayoutConfig = LayoutConfig()) -> Data {
    render(invoice: invoice, config: config)
  }
  private static func render(invoice: Invoice, config: LayoutConfig) -> Data {
    let pageRect = CGRect(x: 0, y: 0, width: config.pageWidth, height: config.pageHeight)
    let data = NSMutableData()
    let consumer = CGDataConsumer(data: data as CFMutableData)!
    var mediaBox = pageRect
    guard let ctx = CGContext(consumer: consumer, mediaBox: &mediaBox, nil) else { return Data() }
    ctx.beginPDFPage(nil)
    let drawer = InvoicePDFDrawer(context: ctx, rect: pageRect, invoice: invoice, config: config)
    drawer.draw()
    ctx.endPDFPage()
    ctx.closePDF()
    return data as Data
  }
}

private func inform(title: String, message: String) {
  let alert = NSAlert()
  alert.messageText = title
  alert.informativeText = message
  alert.addButton(withTitle: "OK")
  alert.runModal()
}

private final class InvoicePDFDrawer {
  let ctx: CGContext
  let rect: CGRect
  let invoice: Invoice
  let config: LayoutConfig
  var cursorY: CGFloat
  let left: CGFloat
  let right: CGFloat
  let lineH: CGFloat
  let baseFont: CGFloat
  init(context: CGContext, rect: CGRect, invoice: Invoice, config: LayoutConfig) {
    self.ctx = context
    self.rect = rect
    self.invoice = invoice
    self.config = config
    self.cursorY = config.topStartY
    self.left = config.marginLeft
    self.right = config.marginRight
    self.lineH = config.lineHeight
    self.baseFont = config.bodyFontSize
  }

  func draw() {
    header()
    parties()
    exchange()
    items()
    totals()
    payment()
  }

  private func font(_ size: CGFloat, bold: Bool = false) -> CTFont {
    FontProvider.verdana(size: size, bold: bold)
  }
  private func setFont(_ size: CGFloat, bold: Bool = false) {
    ctx.setFont(CTFontCopyGraphicsFont(font(size, bold: bold), nil))
    ctx.setFontSize(size)
  }
  private func draw(
    _ text: String, x: CGFloat, y: CGFloat, rightAlign: Bool = false, size: CGFloat? = nil,
    bold: Bool = false
  ) {
    // Build attributed string with explicit CTFont attribute to ensure bold trait respected
    let ctFont = font(size ?? baseFont, bold: bold)
    let attrStr = NSAttributedString(
      string: text,
      attributes: [NSAttributedString.Key(kCTFontAttributeName as String): ctFont])
    let line = CTLineCreateWithAttributedString(attrStr)
    let width = CGFloat(CTLineGetTypographicBounds(line, nil, nil, nil))
    ctx.textPosition = CGPoint(x: rightAlign ? x - width : x, y: y)
    CTLineDraw(line, ctx)
  }
  private func next() { cursorY -= lineH }
  private func line() {
    ctx.setLineWidth(1)
    ctx.move(to: CGPoint(x: left, y: cursorY))
    ctx.addLine(to: CGPoint(x: right, y: cursorY))
    ctx.strokePath()
    next()
  }

  private func header() {
    // Always show Romanian then English translation
    draw("Factură (Invoice)", x: left, y: cursorY, size: baseFont + 4, bold: true)
    next()
    draw(
      local("Seria", en: "Seria (Prefix)") + ": " + invoice.series, x: left, y: cursorY,
      size: baseFont + 2)
    draw(
      local("Număr", en: "Număr (Number)") + ": " + invoice.number, x: right, y: cursorY,
      rightAlign: true, size: baseFont + 2)
    next()
    draw(
      local("Data facturării", en: "Data facturării (Invoice date)") + ": "
        + dateStr(invoice.issueDate), x: left, y: cursorY, size: baseFont + 2)
    draw(
      local("Data scadentă", en: "Data scadentă (Due date)") + ": " + dateStr(invoice.dueDate),
      x: right, y: cursorY, rightAlign: true, size: baseFont + 2)
    next()
    line()
  }

  private func parties() {
    // Provider lines (bold when flagged by isBold or key suffix -B)
    for f in invoice.provider.ordered {
      draw(f.value, x: left, y: cursorY, bold: f.isBold || f.key.hasSuffix("-B"))
      next()
    }
    line()
    // Client lines
    for f in invoice.client.ordered {
      draw(f.value, x: left, y: cursorY, bold: f.isBold || f.key.hasSuffix("-B"))
      next()
    }
    line()
  }

  private func exchange() {
    guard let rate = invoice.exchangeRate else { return }
    draw(
      local("Curs BNR la", en: "Curs BNR la (BNR exchange rate on") + " "
        + dateStr(invoice.issueDate) + local("", en: ")") + ":", x: left, y: cursorY, bold: true)
    next()
    draw(
      "1 \(invoice.currencySource) = \(String(format: "%.2f", rate)) \(invoice.currencyTarget)",
      x: left, y: cursorY)
    next()
    line()
  }
  private func items() {
    // Column positions approximated to Python layout
    let descX = left
    let priceX = left + 230
    let unitX = left + 330
    let qtyX = right
    // Headers bilingual
    draw(local("Descriere", en: "Descriere (Description)"), x: descX, y: cursorY, bold: true)
    draw(local("Pret Unitar", en: "Pret Unitar (Price)"), x: priceX, y: cursorY, bold: true)
    draw(local("Unitate", en: "Unitate (Unit)"), x: unitX, y: cursorY, bold: true)
    draw(
      local("Cantitate", en: "Cantitate (Quantity)"), x: qtyX, y: cursorY, rightAlign: true,
      bold: true)
    next()
    line()
    // Wrap helper (~25 chars)
    func wrap(_ text: String, limit: Int = 25) -> [String] {
      if text.count <= limit { return [text] }
      var lines: [String] = []
      var current = ""
      for word in text.split(separator: " ") {
        if current.isEmpty {
          current = String(word)
          continue
        }
        if current.count + 1 + word.count <= limit {
          current += " " + word
          continue
        }
        lines.append(current)
        current = String(word)
      }
      if !current.isEmpty { lines.append(current) }
      return lines
    }
    for it in invoice.items {
      let descLines = wrap(it.description)
      let maxLines = descLines.count
      for (i, dl) in descLines.enumerated() {
        draw(dl, x: descX, y: cursorY)
        if i == 0 {
          let priceStr = String(format: "%.2f %@", it.unitPrice.amount, it.unitPrice.currency)
          draw(priceStr.replacingOccurrences(of: ".00", with: ""), x: priceX, y: cursorY)
          draw(it.unit, x: unitX, y: cursorY)
          draw(
            String(
              format: it.quantity.truncatingRemainder(dividingBy: 1) == 0 ? "%.0f" : "%.2f",
              it.quantity), x: qtyX, y: cursorY, rightAlign: true)
        }
        next()
      }
      if maxLines == 0 { next() }
    }
    line()
  }
  private func totals() {
    let qtyX = right
    let sourceTotal = invoice.totalSource
    let sourceStr = String(format: "%.1f %@", sourceTotal, invoice.currencySource)
    if let r = invoice.exchangeRate, let tgt = invoice.totalTarget {
      let tgtStr = String(format: "%.2f %@", tgt, invoice.currencyTarget)
      let formula = sourceStr + " x " + String(format: "%.2f", r) + " = " + tgtStr
      draw(
        local("Total", en: "Total") + ": " + formula, x: qtyX, y: cursorY, rightAlign: true,
        bold: true)
    } else {
      draw(
        local("Total", en: "Total") + ": " + sourceStr, x: qtyX, y: cursorY, rightAlign: true,
        bold: true)
    }
    next()
    line()
  }
  private func payment() {
    guard let lines = invoice.paymentLines, !lines.isEmpty else { return }
    for l in lines {
      draw(l.value, x: left, y: cursorY, bold: l.isBold || l.key.hasSuffix("-B"))
      next()
    }
  }
  private func dateStr(_ d: Date) -> String {
    let f = DateFormatter()
    f.dateFormat = "dd/MM/yyyy"
    return f.string(from: d)
  }
  private func local(_ ro: String, en: String) -> String { (invoice.language == "ro" ? ro : en) }
  private func partyLines(_ dict: [String: String]) -> [(String, Bool)] {
    dict.keys.sorted().map { (dict[$0] ?? "", $0.hasSuffix("-B")) }
  }
}
