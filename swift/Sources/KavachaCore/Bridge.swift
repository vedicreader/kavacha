import Foundation
import Network

/// One call the page makes on `window.<js_global>.api`.
public enum BridgeAction: Equatable, Sendable {
    case openFolder(String)
    case pickFolder
    /// Open…: the native chooser for one file or folder
    case pickPath
    /// a folder as `openFolder`, a file where a Finder open sends it
    case openPath(String)
    case recent
    case setBackground(String)
    case setTitle(String, url: String?)
    /// the title bar's style, so the page knows what room to leave
    case titlebar
    /// the pointer entered (true) or left an element whose own class is the drag class; not a page API
    case dragRegion(Bool)
    case unknown(String)
}

/// The page's native bridge: the same `window.pywebview.api` a pywebview app gives it, so the page JavaScript does not change. Its names come from kavacha.json.
public enum Bridge {
    public static var handler: String { Kavacha.config.bridge.handler }
    public static var methods: [String] { Kavacha.config.bridge.methods }

    /// the message `{method, args}` the shim posts, as an action
    public static func route(_ body: Any) -> BridgeAction {
        guard let d = body as? [String: Any], let m = d["method"] as? String else { return .unknown("\(body)") }
        let a = d["args"] as? [Any] ?? []
        let s = { (i: Int) in i < a.count ? a[i] as? String : nil }
        switch m {
        case "open_folder": return s(0).map { $0.isEmpty ? .unknown(m) : .openFolder($0) } ?? .unknown(m)
        case "pick_folder": return .pickFolder
        case "pick_path": return .pickPath
        case "open_path": return s(0).map { $0.isEmpty ? .unknown(m) : .openPath($0) } ?? .unknown(m)
        case "recent": return .recent
        case "set_background": return s(0).flatMap { isColour($0) ? .setBackground($0) : nil } ?? .unknown(m)
        case "set_title": return s(0).map { .setTitle($0, url: s(1)) } ?? .unknown(m)
        case "titlebar": return .titlebar
        case "drag_region": return (a.first as? Bool).map { .dragRegion($0) } ?? .unknown(m)
        default: return .unknown(m)
        }
    }

    /// with a `mac-unified` title bar: tells the launcher when the pointer is over an element whose own class is the drag class, as
    /// WKWebView ignores -webkit-app-region; the launcher drags the window on a mouse-down there
    public static func dragScript(_ c: LauncherConfig = Kavacha.config) -> String {
        """
        (() => {
          let on = false;
          addEventListener('mouseover', e => {
            const t = !!(e.target && e.target.classList && e.target.classList.contains(\(jsString(c.titlebar.drag_class))));
            if (t !== on) { on = t; window.webkit.messageHandlers.\(c.bridge.handler).postMessage({method: 'drag_region', args: [t]}); }
          }, true);
        })();
        """
    }

    static func jsString(_ s: String) -> String { (try? JSONSerialization.data(withJSONObject: [s])).map { String(decoding: $0, as: UTF8.self).dropFirst().dropLast() }.map(String.init) ?? "\"\"" }

    public static func isColour(_ s: String) -> Bool { s.range(of: "^#[0-9a-fA-F]{6}$", options: .regularExpression) != nil }

    /// injected at document start in every page of the server
    public static func shim(_ c: LauncherConfig = Kavacha.config) -> String {
        let b = c.bridge, g = b.js_global
        return """
        (() => {
          if (window.\(g) && window.\(g).api && window.\(g).api.\(b.flag)) return;
          const call = (method, args) => window.webkit.messageHandlers.\(b.handler).postMessage({method, args});
          const api = {\(b.flag): true};
          for (const m of \(b.methods.description)) api[m] = (...args) => call(m, args);
          window.\(g) = {api};
          const ready = () => window.dispatchEvent(new Event('\(g)ready'));
          if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready); else ready();
        })();
        """
    }
}

/// What the launcher does for a control route; the app delegate implements it.
@MainActor public protocol ControlHost: AnyObject {
    /// nil when no window can ask
    func confirm(_ question: String) async -> Bool?
    func installExtra(_ name: String) async -> Bool
    func startUpdate(kind: String, latest: String?) async -> UpdateState
    func updateState() -> UpdateState
    func restartServer() async -> Bool
    func status() -> [String: Any]
    /// whether the launcher issued `nonce` for `path` (one use)
    func checkGrant(_ nonce: String, path: String) -> Bool
}

public struct ControlRequest: Sendable {
    public var method: String
    public var path: String
    public var headers: [String: String]
    public var body: Data
    public init(method: String, path: String, headers: [String: String], body: Data) {
        self.method = method; self.path = path; self.headers = headers; self.body = body
    }
}

/// The routes of the launcher's control server, without the socket. See contract/api-1.md.
public enum ControlRouter {
    public static func tokenOK(_ headers: [String: String], token: String) -> Bool {
        guard !token.isEmpty, let a = headers["authorization"], a.hasPrefix("Bearer ") else { return false }
        let given = Array(a.dropFirst(7).utf8), want = Array(token.utf8)
        guard given.count == want.count else { return false }
        return zip(given, want).reduce(0) { $0 | ($1.0 ^ $1.1) } == 0
    }

    @MainActor public static func handle(_ r: ControlRequest, token: String, host: ControlHost, extras: [String] = Kavacha.config.extras) async -> (Int, [String: Any]) {
        guard tokenOK(r.headers, token: token) else { return (401, ["ok": false, "error": "bad token"]) }
        let body = (try? JSONSerialization.jsonObject(with: r.body)) as? [String: Any] ?? [:]
        switch (r.method, r.path) {
        case ("POST", "/confirm"):
            guard let q = body["question"] as? String else { return (400, ["ok": false, "error": "no question"]) }
            guard let yes = await host.confirm(q) else { return (200, ["ok": false, "no_window": true]) }
            return (200, ["answer": yes])
        case ("POST", "/extras"):
            guard let n = body["name"] as? String, extras.contains(n) else { return (400, ["ok": false, "error": "unknown extra"]) }
            return (200, ["ok": await host.installExtra(n)])
        case ("POST", "/update"):
            guard let k = body["kind"] as? String, ["app", "lock"].contains(k) else { return (400, ["ok": false, "error": "kind is app or lock"]) }
            let u = await host.startUpdate(kind: k, latest: body["latest"] as? String)
            return (200, ["state": u.state, "line": u.line])
        case ("GET", "/update"):
            let u = host.updateState()
            return (200, ["state": u.state, "line": u.line])
        case ("POST", "/restart"): return (200, ["ok": await host.restartServer()])
        case ("GET", "/status"): return (200, host.status())
        case ("POST", "/grant"):
            guard let n = body["nonce"] as? String, let p = body["path"] as? String else { return (400, ["ok": false, "error": "nonce and path"]) }
            return (200, ["ok": host.checkGrant(n, path: p)])
        default: return (404, ["ok": false, "error": "no route \(r.method) \(r.path)"])
        }
    }
}

/// A small HTTP/1.1 server on 127.0.0.1 for the control routes: one request per connection.
public final class ControlServer: @unchecked Sendable {
    public let token: String
    public private(set) var port = 0
    private var listener: NWListener?
    private let q = DispatchQueue(label: "kavacha-control")
    private let handle: @Sendable (ControlRequest) async -> (Int, [String: Any])

    public init(token: String = ControlServer.newToken(), handle: @escaping @Sendable (ControlRequest) async -> (Int, [String: Any])) {
        self.token = token; self.handle = handle
    }

    public static func newToken() -> String {
        var b = [UInt8](repeating: 0, count: 32)
        _ = SecRandomCopyBytes(kSecRandomDefault, b.count, &b)
        return hex(b)
    }

    public var url: String { "http://127.0.0.1:\(port)" }

    public func start() throws {
        let params = NWParameters.tcp
        params.requiredLocalEndpoint = .hostPort(host: "127.0.0.1", port: .any)
        let l = try NWListener(using: params)
        let ready = DispatchSemaphore(value: 0)
        l.stateUpdateHandler = { s in if case .ready = s { ready.signal() } }
        l.newConnectionHandler = { [weak self] c in self?.serve(c) }
        l.start(queue: q)
        listener = l
        _ = ready.wait(timeout: .now() + 5)
        port = Int(l.port?.rawValue ?? 0)
    }

    public func stop() { listener?.cancel() }

    private func serve(_ c: NWConnection) {
        c.start(queue: q)
        read(c, Data())
    }

    private func read(_ c: NWConnection, _ have: Data) {
        c.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] d, _, done, err in
            guard let self else { return c.cancel() }
            let buf = have + (d ?? Data())
            if let req = Self.parse(buf) { return self.answer(c, req) }
            if done || err != nil || buf.count > 1 << 20 { return c.cancel() }
            self.read(c, buf)
        }
    }

    /// a whole request, or nil while bytes are still to come
    static func parse(_ d: Data) -> ControlRequest? {
        guard let end = d.firstRange(of: Data("\r\n\r\n".utf8)) else { return nil }
        let head = String(decoding: d[..<end.lowerBound], as: UTF8.self).components(separatedBy: "\r\n")
        let first = head.first?.split(separator: " ") ?? []
        guard first.count >= 2 else { return nil }
        var h = [String: String]()
        for l in head.dropFirst() { if let i = l.firstIndex(of: ":") { h[l[..<i].lowercased()] = l[l.index(after: i)...].trimmingCharacters(in: .whitespaces) } }
        let n = max(0, Int(h["content-length"] ?? "0") ?? 0), body = d[end.upperBound...]
        guard body.count >= n else { return nil }
        return ControlRequest(method: String(first[0]), path: String(first[1]).components(separatedBy: "?")[0], headers: h, body: Data(body.prefix(n)))
    }

    private func answer(_ c: NWConnection, _ req: ControlRequest) {
        let handle = self.handle
        Task {
            let (code, obj) = await handle(req)
            let body = (try? JSONSerialization.data(withJSONObject: obj)) ?? Data("{}".utf8)
            let head = "HTTP/1.1 \(code) \(code == 200 ? "OK" : "Error")\r\nContent-Type: application/json\r\nContent-Length: \(body.count)\r\nConnection: close\r\n\r\n"
            c.send(content: Data(head.utf8) + body, completion: .contentProcessed { _ in c.cancel() })
        }
    }
}
