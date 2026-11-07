// swift-tools-version: 6.0
// kavacha's native launcher for thin apps (contract/api-1.md). The sources are under swift/.
import PackageDescription

let v5: [SwiftSetting] = [.swiftLanguageMode(.v5)]

let package = Package(
    name: "Kavacha",
    platforms: [.macOS(.v14)],
    products: [
        // Tier B: an app builds its own launcher on these
        .library(name: "KavachaCore", targets: ["KavachaCore"]),
        .library(name: "KavachaApp", targets: ["KavachaApp"]),
        // Tier A: the prebuilt launcher, configured by kavacha.json
        .executable(name: "kavacha-launcher", targets: ["kavacha-launcher"]),
    ],
    targets: [
        // no AppKit: config, paths, child env, lock hash, SSHSIG, manifests, the env store, the channel, the supervisor, setup phases, the bridge router, the control server
        .target(name: "KavachaCore", path: "swift/Sources/KavachaCore", swiftSettings: v5),
        // the window layer: windows, menus, key equivalents, navigation policy, the Dock menu, the app delegate
        .target(name: "KavachaApp", dependencies: ["KavachaCore"], path: "swift/Sources/KavachaApp", swiftSettings: v5),
        .executableTarget(name: "kavacha-launcher", dependencies: ["KavachaApp"], path: "swift/Sources/kavacha-launcher", swiftSettings: v5),
        .testTarget(name: "KavachaCoreTests", dependencies: ["KavachaCore"], path: "swift/Tests/KavachaCoreTests", swiftSettings: v5),
        // no window is ordered on screen
        .testTarget(name: "KavachaAppTests", dependencies: ["KavachaApp"], path: "swift/Tests/KavachaAppTests", swiftSettings: v5),
    ]
)
