import AppKit
import KavachaCore

/// The launcher's entry points: the app, and the headless checks `--lock-test` and `--check-menu`.
public enum Launcher {
    /// kavacha.json from the bundle into `Kavacha.config`; the reason when it cannot be used
    @discardableResult
    public static func configure(_ bundle: Bundle = .main) -> String? {
        guard let u = bundle.resourceURL?.appending(path: "kavacha.json") else { return "no Resources folder" }
        do { Kavacha.config = try LauncherConfig.load(u); return nil }
        catch LauncherConfig.Refusal.newerAPI(let n) { return "kavacha.json asks for API \(n); this launcher has API \(LauncherAPI.version)" }
        catch { return "no good kavacha.json: \(error)" }
    }

    /// the app, with its windows; it returns only when the app quits
    @MainActor public static func run() {
        let app = NSApplication.shared, delegate = AppDelegate()
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
    }

    /// a damaged bundle says so and stops
    @MainActor public static func refuse(_ why: String) -> Never {
        FileHandle.standardError.write(Data("kavacha-launcher: \(why)\n".utf8))
        NSApplication.shared.setActivationPolicy(.regular)
        let a = NSAlert(); a.messageText = "This copy of the app is damaged. Install it again."; a.informativeText = why; a.runModal()
        exit(1)
    }

    /// builds the env of `lock` in `work` as the app does, with the bundled uv and childenv.json, and prints it; no window
    public static func lockTest(lock: URL, work: URL, bundle: Bundle = .main) -> Int32 {
        let res = bundle.resourceURL!, uv = bundle.bundleURL.appending(path: "Contents/Helpers/uv")
        let sem = DispatchSemaphore(value: 0)
        nonisolated(unsafe) var code: Int32 = 1
        Task.detached {
            do {
                let spec = try ChildEnv.load(res.appending(path: "childenv.json"))
                let v = Run.output(uv, ["--version"])?.split(separator: " ").dropFirst().first.map(String.init) ?? ""
                let store = EnvStore(paths: Paths(support: work.appending(path: "support"), caches: work.appending(path: "caches")), spec: spec, uv: uv, uvVersion: v)
                let h = try await store.build(lock: lock, n: 0, extras: [])
                print(store.paths.env(h).path); code = 0
            } catch { FileHandle.standardError.write(Data("lock test: \(error)\n".utf8)) }
            sem.signal()
        }
        sem.wait()
        return code
    }

    /// what is wrong with the menu bar `menu.json` gives (`{menus, launcher}`), checked with no window; [] when nothing is
    @MainActor public static func checkMenu(_ url: URL) -> [String] {
        guard let d = (try? JSONSerialization.jsonObject(with: Data(contentsOf: url))) as? [String: Any], let menus = d["menus"] as? [[String: Any]] else { return ["\(url.path) has no menus"] }
        return MenuCheck.problems(menus, launcher: d["launcher"] as? [[String: Any]])
    }
}

/// The checks of a menu bar that need no window: each chord is on its row, a key-down as the US keyboard sends it runs that row, no two
/// rows share a chord, and no action row takes ⌘Z.
@MainActor public enum MenuCheck {
    /// the US keyboard's key codes (Carbon kVK_*), so the event is the one the keyboard sends
    public static let usKeys: [String: UInt16] = ["a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9, "b": 11, "q": 12, "w": 13, "e": 14,
        "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29, "]": 30,
        "o": 31, "u": 32, "[": 33, "i": 34, "p": 35, "\r": 36, "l": 37, "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44, "n": 45, "m": 46,
        ".": 47, "\t": 48, " ": 49, "`": 50, "\u{1b}": 53, "\u{F702}": 123, "\u{F703}": 124, "\u{F701}": 125, "\u{F700}": 126]

    /// a key-down as the US keyboard gives it: its key code, shift applied to the character, an arrow with the function flag
    public static func keyDown(_ key: String, _ mask: NSEvent.ModifierFlags) -> NSEvent {
        var flags = mask
        if let u = key.unicodeScalars.first?.value, (0xF700...0xF8FF).contains(u) { flags.formUnion([.function, .numericPad]) }
        let chars = mask.contains(.shift) ? Menus.usShift[key] ?? key.uppercased() : key
        return NSEvent.keyEvent(with: .keyDown, location: .zero, modifierFlags: flags, timestamp: 0, windowNumber: 0, context: nil,
                                characters: chars, charactersIgnoringModifiers: chars, isARepeat: false, keyCode: usKeys[key] ?? 0)!
    }

    /// every row with a key, in menu order
    public static func keyed(_ bar: NSMenu) -> [NSMenuItem] { bar.items.compactMap(\.submenu).flatMap(\.items).filter { !$0.keyEquivalent.isEmpty } }
    static func chord(_ i: NSMenuItem) -> String { "\(i.keyEquivalent)|\(i.keyEquivalentModifierMask.intersection(.deviceIndependentFlagsMask).rawValue)" }

    /// each row of `menus` with a chord: its menu, title, key, mask, and what it runs
    public static func chords(_ menus: [[String: Any]]) -> [(menu: String, title: String, key: String, mask: NSEvent.ModifierFlags, what: String)] {
        menus.flatMap { m in (m["items"] as? [[String: Any]] ?? []).compactMap { r in
            guard let k = r["key"] as? String, let mask = r["mask"] as? Int else { return nil }
            let what = (r["action"] as? String).map(Menus.js(action:)) ?? r["selector"] as? String ?? r["js"] as? String ?? ""
            return (m["title"] as? String == "__app__" ? Kavacha.config.name : m["title"] as? String ?? "", r["title"] as? String ?? "", k, NSEvent.ModifierFlags(rawValue: UInt(mask)), what)
        } }
    }

    public static func problems(_ menus: [[String: Any]], launcher: [[String: Any]]? = nil) -> [String] {
        var out = [String](), ran = [String]()
        let runner = MenuRunner { ran.append($0) }, bar = Menus.build(menus, launcher: launcher ?? Menus.launcher, runner: runner), probe = Probe()
        let built = Dictionary(bar.items.compactMap(\.submenu).flatMap { m in m.items.map { ("\(m.title)/\($0.title)", $0) } }, uniquingKeysWith: { a, _ in a })
        let rows = chords(menus)
        for r in rows {
            guard let it = built["\(r.menu)/\(r.title)"] else { out.append("no item for \(r.menu)/\(r.title)"); continue }
            let (k, m) = Menus.appKit(r.key, r.mask)
            if it.keyEquivalent != k || it.keyEquivalentModifierMask != m { out.append("\(r.menu)/\(r.title) is not built with its chord") }
        }
        var seen = [String: String]()
        for i in keyed(bar) {
            let what = (i.representedObject as? String) ?? i.action.map(NSStringFromSelector) ?? i.title
            if let was = seen[chord(i)], was != what { out.append("\(chord(i)): \(was) and \(what)") } else { seen[chord(i)] = what }
            if i.keyEquivalent == "z", i.keyEquivalentModifierMask.intersection(.deviceIndependentFlagsMask) == .command, i.target != nil { out.append("\(i.title) takes ⌘Z") }
        }
        for i in keyed(bar) where i.target !== runner { i.target = probe }
        var done = Set<String>()
        for r in rows where done.insert("\(r.key)|\(r.mask.rawValue)").inserted {
            ran = []; probe.got = []
            if !bar.performKeyEquivalent(with: keyDown(r.key, r.mask)) { out.append("\(r.title) \(r.key) \(r.mask.rawValue) is not dispatched"); continue }
            if ran + probe.got != [r.what] { out.append("\(r.title) \(r.key) \(r.mask.rawValue) ran \(ran + probe.got), not \(r.what)") }
        }
        return out
    }

    /// the target a selector row is moved to, so AppKit's dispatch can be seen without a window or the app acting
    public final class Probe: NSObject {
        public var got = [String]()
        @objc func cut(_ s: Any?) { got.append("cut:") }
        @objc func copy(_ s: Any?) { got.append("copy:") }
        @objc func paste(_ s: Any?) { got.append("paste:") }
        @objc func selectAll(_ s: Any?) { got.append("selectAll:") }
        @objc func undo(_ s: Any?) { got.append("undo:") }
        @objc func redo(_ s: Any?) { got.append("redo:") }
        @objc func toggleFullScreen(_ s: Any?) { got.append("toggleFullScreen:") }
        @objc func performMiniaturize(_ s: Any?) { got.append("performMiniaturize:") }
        @objc func performZoom(_ s: Any?) { got.append("performZoom:") }
        @objc func performClose(_ s: Any?) { got.append("performClose:") }
        @objc func arrangeInFront(_ s: Any?) { got.append("arrangeInFront:") }
        @objc func hide(_ s: Any?) { got.append("hide:") }
        @objc func hideOtherApplications(_ s: Any?) { got.append("hideOtherApplications:") }
        @objc func unhideAllApplications(_ s: Any?) { got.append("unhideAllApplications:") }
        @objc func terminate(_ s: Any?) { got.append("terminate:") }
        @objc func orderFrontStandardAboutPanel(_ s: Any?) { got.append("orderFrontStandardAboutPanel:") }
    }
}
