import AppKit
import CoreText
import Foundation

enum FontProvider {
  // Attempts to create Verdana / Verdana-Bold CTFont. Falls back to system if unavailable.
  static func verdana(size: CGFloat, bold: Bool = false) -> CTFont {
    // Primary attempt: direct named font (system usually has Verdana installed)
    let baseName: CFString = (bold ? "Verdana-Bold" : "Verdana") as CFString
    let direct = CTFontCreateWithName(baseName, size, nil)
    let post = CTFontCopyPostScriptName(direct) as String
    if post.lowercased().contains("verdana") {
      // If bold requested but font name doesn't actually contain 'bold', try symbolic trait copy.
      if bold && !post.lowercased().contains("bold") {
        if let withTrait = CTFontCreateCopyWithSymbolicTraits(
          direct, size, nil, CTFontSymbolicTraits.traitBold, CTFontSymbolicTraits.traitBold)
        {
          return withTrait
        }
      }
      return direct
    }
    // Fallback to system font(s)
    let sys = bold ? NSFont.boldSystemFont(ofSize: size) : NSFont.systemFont(ofSize: size)
    let sysCT = CTFontCreateWithName(sys.fontName as CFString, size, nil)
    if bold {
      // Ensure bold trait present even if boldSystemFont returned a non-bold variant in PDF context
      if let withTrait = CTFontCreateCopyWithSymbolicTraits(
        sysCT, size, nil, CTFontSymbolicTraits.traitBold, CTFontSymbolicTraits.traitBold)
      {
        return withTrait
      }
    }
    return sysCT
  }

  // If you later bundle TTF files (e.g. Verdana.ttf), you could register them dynamically:
  // static func registerIfNeeded(url: URL) { CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil) }
}
