import Foundation
import Testing
@testable import KavachaCore

/// contract/fixtures, which the Python side reads too, and the golden Leela config.
func fixture(_ name: String) -> Any { try! JSONSerialization.jsonObject(with: Data(contentsOf: contract.appending(path: name))) }

@Suite struct ContractTests {
    @Test func theLockHashVector() throws {
        let v = fixture("lock_hash/vector.json") as! [String: Any], d = contract.appending(path: "lock_hash")
        #expect(try LockHash.hash(dir: d, uv: v["uv"] as! String) == v["hash"] as! String)
        for o in v["others"] as! [[String: String]] { #expect(try LockHash.hash(dir: d, uv: o["uv"]!) == o["hash"]!) }
    }

    @Test func theSSHSIGFixtures() throws {
        let msg = try Data(contentsOf: fixtures.appending(path: "message.json"))
        let sig = { (n: String) in try String(contentsOf: fixtures.appending(path: "\(n).sig"), encoding: .utf8) }
        for n in ["main", "emergency"] { #expect(throws: Never.self) { try SSHSig.verify(message: msg, signature: try sig(n), keys: fixtureKeys, namespace: "app-lock") } }
        #expect(throws: SSHSigError.unknownKey) { try SSHSig.verify(message: msg, signature: try sig("stranger"), keys: fixtureKeys, namespace: "app-lock") }
        #expect(throws: SSHSigError.namespace) { try SSHSig.verify(message: msg, signature: try sig("wrongns"), keys: fixtureKeys, namespace: "app-lock") }
    }

    @Test func theChildEnvCases() throws {
        for c in fixture("childenv_cases.json") as! [[String: Any]] {
            let spec = try JSONDecoder().decode(ChildEnv.self, from: JSONSerialization.data(withJSONObject: c["spec"]!))
            let parent = c["parent"] as! [String: String], home = c["home"] as! String
            #expect(spec.uvEnv(parent, home: home, vals: c["vals"] as! [String: String]) == c["uv_env"] as! [String: String])
            #expect(spec.serverEnv(parent, home: home, extra: c["extra"] as! [String: String]) == c["server_env"] as! [String: String])
            #expect(spec.syncArgs(lock: URL(fileURLWithPath: c["lock"] as! String), extras: ["a"], inexact: true) == c["sync"] as! [String])
            #expect(spec.serverArgs(port: c["port"] as! Int) == c["server_args"] as! [String])
        }
    }

    @Test func theBridgeCases() {
        for c in fixture("bridge_cases.json") as! [[String: Any]] {
            let a = c["action"] as! [String: Any], got = Bridge.route(c["body"]!)
            let want: BridgeAction = if let p = a["open_folder"] as? String { .openFolder(p) } else if a["pick_folder"] != nil { .pickFolder } else if a["pick_path"] != nil { .pickPath }
                else if let p = a["open_path"] as? String { .openPath(p) } else if a["recent"] != nil { .recent } else if let b = a["set_background"] as? String { .setBackground(b) }
                else if let t = a["set_title"] as? String { .setTitle(t, url: a["url"] as? String) } else { .unknown(a["unknown"] as! String) }
            #expect(got == want, "\(c["body"]!)")
        }
    }

    /// a built env for `h`: its marker and an executable server
    func built(_ s: EnvStore, _ h: String) throws {
        try FileManager.default.createDirectory(at: s.paths.server(h).deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data("#!/bin/sh\n".utf8).write(to: s.paths.server(h)); try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: s.paths.server(h).path)
        try s.writeMarker(EnvMarker(hash: h, n: 0, uv: "0.13.6", extras: [], built: 0))
    }

    @Test func theStateCases() throws {
        let d = fixture("state_cases.json") as! [String: Any]
        for c in d["load"] as! [[String: Any]] {
            let s = try JSONDecoder().decode(EnvState.self, from: JSONSerialization.data(withJSONObject: c["json"]!)), w = c["want"] as! [String: Any]
            #expect(s.current == w["current"] as? String && s.previous == w["previous"] as? String && s.pending == w["pending"] as? String, "\(c["name"]!)")
            #expect(s.highest_n == w["highest_n"] as! Int && s.bad == w["bad"] as! [String] && s.extras == w["extras"] as! [String] && s.early_crashes == w["early_crashes"] as! Int)
        }
        for c in d["moves"] as! [[String: Any]] {
            let s = store(), name = c["name"] as! String
            for h in c["built"] as! [String] { try built(s, h) }
            var st = try JSONDecoder().decode(EnvState.self, from: JSONSerialization.data(withJSONObject: c["before"]!)); st.locks = st.locks.isEmpty ? [:] : st.locks
            try s.save(st)
            switch c["op"] as! String {
            case "switch_at_launch": try s.switchAtLaunch()
            case "rollback_bad": try s.rollback(bad: true)
            default: try s.rollback(bad: false)
            }
            let got = try JSONSerialization.jsonObject(with: JSONEncoder().encode(s.load())) as! [String: Any]
            for (k, v) in c["after"] as! [String: Any] {
                #expect("\(got[k] ?? NSNull())" == "\(v)", "\(name): \(k) is \(got[k] ?? "nil"), not \(v)")
            }
        }
    }

    @Test func theManifestCases() throws {
        let d = fixture("manifest_cases.json") as! [String: Any]
        for c in d["manifests"] as! [[String: Any]] {
            let dir = tempDir(), set = c["set"] as! [String: Any], name = c["name"] as! String
            let m = makeLock(dir, n: 7, uv: c["hash_uv"] as? String ?? "0.13.6") { m in
                var o = try! JSONSerialization.jsonObject(with: JSONEncoder().encode(m)) as! [String: Any]
                for (k, v) in set { o[k] = v }
                m = try! JSONDecoder().decode(Manifest.self, from: JSONSerialization.data(withJSONObject: o))
            }
            let got: String
            do {
                switch try LockCheck.check(dir: dir, keys: fixtureKeys, app: facts, highest: c["highest"] as? Int ?? -1, bad: c["bad"] != nil ? [m.hash] : []) {
                case .ok: got = "ok"
                case .needsApp: got = "needsApp"
                }
            } catch let r as LockRefusal {
                got = switch r { case .replay: "replay"; case .platform: "platform"; case .macOS: "macOS"; case .lockHash: "lockHash"; case .fileHash: "fileHash"; case .bad: "bad"; default: "\(r)" }
            }
            #expect(got == c["want"] as! String, "\(name)")
        }
        for c in d["pointers"] as! [[String: Any]] {
            let f = tempDir().appending(path: "p.json")
            var o: [String: Any] = ["n": 4, "manifest_sha256": "ab", "published": "2026-11-06T00:00:00Z", "channel": c["channel"]!]
            for (k, v) in c["extra"] as? [String: Any] ?? [:] { o[k] = v }
            try JSONSerialization.data(withJSONObject: o).write(to: f)
            let r = Result { try LockCheck.pointer(Data(contentsOf: f), signature: Data(contentsOf: sign(f)), keys: fixtureKeys, name: c["asked"] as! String) }
            let got = switch r { case .success: "ok"; case .failure(let e): (e as? LockRefusal).map { if case .pointer = $0 { "pointer" } else { "\($0)" } } ?? "\(e)" }
            #expect(got == c["want"] as! String, "\(c["name"]!)")
        }
    }
}

/// The golden test: Leela's spec gives the names Leela 1.0 shipped with.
@Suite struct LeelaGoldenTests {
    let leela = try! LauncherConfig.load(contract.appending(path: "leela/kavacha.json"))

    @Test func theFoldersAndFilesAreLeelas() {
        let p = Paths.user(leela)
        #expect(p.support.path.hasSuffix("Library/Application Support/Leela") && p.caches.path.hasSuffix("Library/Caches/Leela"))
        #expect(p.marker("0123456789abcdef00").lastPathComponent == ".leela-env.json" && p.server("0123456789abcdef00").path.hasSuffix("envs/0123456789abcdef/bin/leela"))
        #expect(p.state.lastPathComponent == "state.json" && p.runLock.lastPathComponent == "run.lock" && p.uvCache.path.hasSuffix("Caches/Leela/uv"))
    }

    @Test func theNamesTheServerSeesAreLeelas() async throws {
        #expect(leela.sig_ns == "leela-lock" && leela.lock_project == "leela-lock" && leela.cask == "leela" && leela.identifier == "org.vedicreader.leela")
        #expect(Channel.isTest(["LEELA_LOCK_CHANNEL": "test"], prefix: leela.env_prefix) && !Channel.isTest(["APP_LOCK_CHANNEL": "test"], prefix: leela.env_prefix))
        #expect(leela.channel == "https://github.com/vedicreader/leela/releases/download")
        let s = store(), lock = tempDir(); makeLock(lock, n: 3)
        let h = try await s.build(lock: lock, n: 3)
        let l = ServerCommand.launch(store: s, port: 5, hash: h, host: HostInfo(url: "u", token: "t", appVersion: "1.0.0", bundle: "/b", uv: URL(fileURLWithPath: "/uv")), prefix: leela.env_prefix)
        #expect(Set(l.env.keys.filter { $0.hasPrefix("LEELA_") }) == ["LEELA_HOST_URL", "LEELA_APP_VERSION", "LEELA_APP_BUNDLE", "LEELA_LOCK_N", "LEELA_ENV_HASH", "LEELA_UV"])
    }

    @Test func theBridgeIsLeelas() {
        let js = Bridge.shim(leela)
        #expect(js.contains("window.webkit.messageHandlers.leela.postMessage") && js.contains("window.pywebview.api.__leela") && js.contains("window.pywebview = {api}") && js.contains("'pywebviewready'"))
        #expect(leela.bridge.methods == ["open_folder", "pick_folder", "pick_path", "open_path", "recent", "set_background", "set_title"])
    }

    @Test func brewUpgradesTheLeelaCask() throws {
        let d = tempDir(), brew = d.appending(path: "bin/brew")
        try FileManager.default.createDirectory(at: brew.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data("#!/bin/sh\n".utf8).write(to: brew); try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: brew.path)
        try FileManager.default.createDirectory(at: d.appending(path: "Caskroom/leela"), withIntermediateDirectories: true)
        #expect(BrewUpgrade.find(app: URL(fileURLWithPath: "/Applications/Leela.app"), places: [brew.path], cask: leela.cask, name: leela.name) == brew)
        #expect(BrewUpgrade(app: URL(fileURLWithPath: "/Applications/Leela.app"), places: [brew.path], config: leela).cask == "leela")
    }

    @Test func stateJsonKeepsItsKeys() throws {
        let o = try JSONSerialization.jsonObject(with: JSONEncoder().encode(EnvState())) as! [String: Any]
        #expect(Set(o.keys) == ["highest_n", "bad", "locks", "extras", "early_crashes", "proven", "held", "pruned"], "nil keys are left out, as before")
    }

    @Test func theWindowNamesAreLeelas() {
        #expect(leela.window.home == "leela:home" && leela.window.title_prefix == "leela — " && leela.window.size == [1440, 900] && leela.window.min_size == [900, 560])
        #expect(leela.menu_action_js == "leeAct({action})" && leela.debug_env == "LEELA_WEBVIEW_DEBUG" && leela.sites["list"] == "/app/sites" && leela.titlebar.unified)
    }
}
