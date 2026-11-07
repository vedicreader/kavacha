import AppKit
import Foundation
import Testing
import WebKit
@testable import KavachaApp

/// The server's menu bar as `make test` wrote it from the Python source, with the default keymap: `KAVACHA_MENU_JSON`.
func menuJSON() throws -> [[String: Any]] {
    let p = try #require(ProcessInfo.processInfo.environment["KAVACHA_MENU_JSON"], "run through make test, which writes the server's menu.json")
    let d = try #require(try JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: p))) as? [String: Any])
    return try #require(d["menus"] as? [[String: Any]])
}

typealias Probe = MenuCheck.Probe
@MainActor func keyDown(_ key: String, _ mask: NSEvent.ModifierFlags) -> NSEvent { MenuCheck.keyDown(key, mask) }
@MainActor func keyed(_ bar: NSMenu) -> [NSMenuItem] { MenuCheck.keyed(bar) }
func chord(_ i: NSMenuItem) -> String { "\(i.keyEquivalent)|\(i.keyEquivalentModifierMask.intersection(.deviceIndependentFlagsMask).rawValue)" }

@MainActor @Suite(.serialized) struct ShortcutTests {
    func chords(_ menus: [[String: Any]]) -> [(menu: String, title: String, key: String, mask: NSEvent.ModifierFlags, what: String)] { MenuCheck.chords(menus) }

    @Test func everyRowWithAKeyIsBuiltWithThatChord() throws {
        let menus = try menuJSON(), bar = Menus.build(menus, runner: MenuRunner { _ in })
        let built = Dictionary(bar.items.compactMap(\.submenu).flatMap { m in m.items.map { ("\(m.title)/\($0.title)", $0) } }, uniquingKeysWith: { a, _ in a })
        let rows = chords(menus)
        for r in rows {
            let it = try #require(built["\(r.menu)/\(r.title)"], "no item for \(r.menu)/\(r.title)")
            let (k, m) = Menus.appKit(r.key, r.mask)
            #expect(it.keyEquivalent == k && it.keyEquivalentModifierMask == m, "\(r.menu)/\(r.title)")
        }
        #expect(rows.count > 50)
    }

    @Test func eachChordFromTheKeyboardReachesItsRowAndRunsTheRowsJavaScript() throws {
        let menus = try menuJSON()
        var ran = [String]()
        let runner = MenuRunner { ran.append($0) }, bar = Menus.build(menus, runner: runner), probe = Probe()
        for i in keyed(bar) where i.target !== runner { i.target = probe }
        // the launcher's own rows, and every row of the server's bar; the first in menu order with a chord is the one AppKit picks
        let own: [(String, String, NSEvent.ModifierFlags, String)] = [("Undo", "z", .command, "undo:"), ("Redo", "z", [.command, .shift], "redo:"),
            ("Close Window", "w", [.command, .shift], "performClose:"), ("Quit", "q", .command, "terminate:"), ("Hide", "h", .command, "hide:"),
            ("Hide Others", "h", [.command, .option], "hideOtherApplications:")]
        var seen = Set<String>()
        for (title, key, mask, what) in own + chords(menus).map({ ($0.title, $0.key, $0.mask, $0.what) }) where seen.insert("\(key)|\(mask.rawValue)").inserted {
            ran = []; probe.got = []
            #expect(bar.performKeyEquivalent(with: keyDown(key, mask)), "\(title) \(key) \(mask.rawValue) is not dispatched")
            #expect(ran + probe.got == [what], "\(title) \(key) \(mask.rawValue)")
        }
        #expect(seen.count > 50)
    }

    @Test func aChordWithoutShiftDoesNotFireItsShiftedRow() throws {
        // ⌘F is Find across cells and ⌘⇧F Search code; with shift spelled as a flag on a lower case key one ran the other
        var ran = [String]()
        let runner = MenuRunner { ran.append($0) }, bar = Menus.build(try menuJSON(), runner: runner)
        #expect(bar.performKeyEquivalent(with: keyDown("f", .command)))
        #expect(ran == [Menus.js(action: "find_in_file")])
        // ⌥↩ is Run and insert below and ⌥⇧↩ Run the selection: ↩ has no case, and AppKit let the first take both
        ran = []
        #expect(bar.performKeyEquivalent(with: keyDown("\r", [.option, .shift])) && ran == [Menus.js(action: "run_selection")])
        ran = []
        #expect(bar.performKeyEquivalent(with: keyDown("\r", .option)) && ran == [Menus.js(action: "run_insert")])
        #expect(Menus.appKit("o", [.command, .shift]) == ("O", .command) && Menus.appKit("/", [.command, .shift]) == ("?", .command))
        #expect(Menus.appKit("p", .command) == ("p", .command) && Menus.appKit("\u{F701}", [.command, .shift]) == ("\u{F701}", [.command, .shift]))
    }

    @Test func actionRowsRunLeeActWithTheActionName() throws {
        let menus = try menuJSON()
        var ran = [String]()
        let runner = MenuRunner { ran.append($0) }, bar = Menus.build(menus, runner: runner)
        #expect(bar.performKeyEquivalent(with: keyDown("p", .command)))
        #expect(ran == ["leeAct(\"quick_open\")"])
        #expect(Menus.js(action: "a\"b") == "leeAct(\"a\\\"b\")")
    }

    @Test func noTwoDifferentRowsShareAChord() throws {
        let bar = Menus.build(try menuJSON(), runner: MenuRunner { _ in })
        var seen = [String: String]()
        for i in keyed(bar) {
            let what = (i.representedObject as? String) ?? i.action.map(NSStringFromSelector) ?? i.title
            if let was = seen[chord(i)] { #expect(was == what, "\(chord(i)): \(was) and \(what)") } else { seen[chord(i)] = what }
        }
    }

    @Test func theLaunchersOwnRowsAreThere() throws {
        let bar = Menus.build(try menuJSON(), runner: MenuRunner { _ in })
        let all = bar.items.compactMap(\.submenu).flatMap(\.items)
        func has(_ sel: String, _ key: String, _ mask: NSEvent.ModifierFlags) -> Bool {
            all.contains { $0.action == Selector((sel)) && $0.keyEquivalent == key && $0.keyEquivalentModifierMask == mask && $0.target == nil }
        }
        #expect(has("terminate:", "q", .command) && has("hide:", "h", .command) && has("hideOtherApplications:", "h", [.command, .option]))
        #expect(has("performClose:", "W", .command) && has("undo:", "z", .command) && has("redo:", "Z", .command))
        #expect(all.contains { $0.action == #selector(NSApplication.unhideAllApplications(_:)) } && all.contains { $0.title == "Services" && $0.submenu != nil })
        #expect(has("performMiniaturize:", "m", .command) && has("toggleFullScreen:", "f", [.command, .control]))
    }

    @Test func theLaunchersRowsAreKavachasLauncherRows() throws {
        // the server's /app/menu.json carries kavacha's LAUNCHER_ROWS; the copy the launcher uses before the server answers must match
        let p = try #require(ProcessInfo.processInfo.environment["KAVACHA_MENU_JSON"])
        let d = try #require(try JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: p))) as? [String: Any])
        let served = try #require(d["launcher"] as? [[String: Any]])
        func key(_ r: [String: Any]) -> String { "\(r["selector"] ?? "")|\(r["key"] ?? "")|\(r["mask"] ?? "")" }
        #expect(served.map(key) == Menus.launcher.map(key))
    }

    @Test func theHeadlessMenuCheckFindsNothingWrong() throws {
        // the same checks `kavacha-launcher --check-menu <menu.json>` runs
        let p = try #require(ProcessInfo.processInfo.environment["KAVACHA_MENU_JSON"])
        #expect(Launcher.checkMenu(URL(fileURLWithPath: p)) == [])
    }

    @Test func undoIsAnEditingRowNeverAnAction() throws {
        // the page sees ⌘Z first (the notebook's own undo); a row that runs an action on it would run twice
        // the runner is kept: a menu item holds its target weakly, and a freed runner left every action row looking like an editing row
        let runner = MenuRunner { _ in }, bar = Menus.build(try menuJSON(), runner: runner)
        for i in keyed(bar) where i.keyEquivalent == "z" && i.keyEquivalentModifierMask == .command { #expect(i.target == nil, "\(i.title) takes ⌘Z") }
        #expect(keyed(bar).contains { $0.target === runner }, "action rows point at the runner")
    }

    @Test func theFallbackBarHasTheEditingRowsBeforeTheServerAnswers() {
        let bar = Menus.build(Menus.fallback, runner: MenuRunner { _ in })
        let edit = bar.items.compactMap(\.submenu).first { $0.title == "Edit" }
        let sels = Set(edit?.items.compactMap { $0.action.map(NSStringFromSelector) } ?? [])
        #expect(sels.isSuperset(of: ["cut:", "copy:", "paste:", "selectAll:", "undo:", "redo:"]))
        #expect(bar.items[0].submenu?.items.contains { $0.action == #selector(NSApplication.terminate(_:)) } == true)
    }

    @Test func editingShortcutsGoToTheWebViewThroughTheResponderChain() throws {
        // a window never ordered on screen: the web view is its first responder; cut:, copy:, paste: sent to nil stop at it, and undo:
        // and redo: at the window, which uses the web view's undo manager. No row takes these keys for an action.
        let ws = Windows()
        let (w, v) = ws.make(URL(string: "http://127.0.0.1:1/")!, title: "t")
        #expect(!w.isVisible && w.firstResponder === v && w.initialFirstResponder === v)
        func first(_ s: Selector) -> NSResponder? { sequence(first: v as NSResponder, next: \.nextResponder).first { $0.responds(to: s) } }
        for s in ["cut:", "copy:", "paste:", "selectAll:"] { #expect(first(Selector((s))) === v, "\(s)") }
        for s in ["undo:", "redo:"] { #expect(first(Selector((s))) === w, "\(s)") }
        #expect(v.undoManager != nil)
        let bar = Menus.build(try menuJSON(), runner: MenuRunner { _ in })
        for i in keyed(bar) where ["x", "c", "v", "a", "z", "Z"].contains(i.keyEquivalent) && i.keyEquivalentModifierMask == .command {
            #expect(i.target == nil && first(i.action!) != nil, "\(i.title) does not reach the web view")
        }
        w.close()
    }
}
