import AppKit
import KavachaApp
import KavachaCore

// kavacha's launcher, configured by Resources/kavacha.json. Headless: `--lock-test <lock> <work>` builds an env as the app does;
// `--check-menu <menu.json>` checks a menu bar with no window.
let args = CommandLine.arguments
let why = Launcher.configure()
if let i = args.firstIndex(of: "--check-menu"), i + 1 < args.count {
    let bad = MainActor.assumeIsolated { Launcher.checkMenu(URL(fileURLWithPath: args[i + 1])) }
    for b in bad { print(b) }
    print(bad.isEmpty ? "menu ok" : "\(bad.count) problems")
    exit(bad.isEmpty ? 0 : 1)
}
if let why { MainActor.assumeIsolated { Launcher.refuse(why) } }
if let i = args.firstIndex(of: "--lock-test"), i + 2 < args.count {
    exit(Launcher.lockTest(lock: URL(fileURLWithPath: args[i + 1]), work: URL(fileURLWithPath: args[i + 2])))
}
MainActor.assumeIsolated { Launcher.run() }
