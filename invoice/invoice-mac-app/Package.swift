// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "InvoiceApp",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "InvoiceApp", targets: ["InvoiceApp"])
    ],
    dependencies: [
        // Add networking / PDF / UI helper packages here later if desired
    ],
    targets: [
        .executableTarget(
            name: "InvoiceApp",
            resources: [
                .process("Resources")
            ]
        )
    ]
)
