import Foundation

@inline(__always)
func debugPublish(_ tag: String, _ message: String = "", file: String = #fileID, line: Int = #line)
{
  // Logs disabled.
}
