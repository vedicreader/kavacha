import Foundation

/// What the launcher tells its server. The token goes on stdin only; the env carries the rest.
public struct HostInfo: Sendable {
    public var url: String
    public var token: String
    public var appVersion: String
    public var bundle: String
    public var uv: URL
    public init(url: String, token: String, appVersion: String, bundle: String, uv: URL) {
        self.url = url; self.token = token; self.appVersion = appVersion; self.bundle = bundle; self.uv = uv
    }
}

public enum ServerCommand {
    /// `<server> <server_args>` from env `hash`, with the token as its first stdin line
    public static func launch(store: EnvStore, port: Int, hash: String, host: HostInfo, prefix: String = Kavacha.config.env_prefix) -> Launch {
        let n = store.load().locks[hash] ?? 0, p = prefix
        let extra = [p + "HOST_URL": host.url, p + "APP_VERSION": host.appVersion, p + "APP_BUNDLE": host.bundle,
                     p + "LOCK_N": String(n), p + "ENV_HASH": hash, p + "UV": host.uv.path]
        return Launch(executable: store.paths.server(hash), args: store.spec.serverArgs(port: port),
                      env: store.spec.serverEnv(store.parent, home: store.home, extra: extra),
                      cwd: store.paths.support, stdinLine: host.token)
    }
}

/// One-time grants: the launcher proves to its server that it asked for a folder, without ever sending the token there.
/// A nonce is good once, for one path, for a minute.
public final class GrantBook: @unchecked Sendable {
    private var issued: [String: (path: String, until: Date)] = [:]
    private let q = NSLock()
    public var ttl: TimeInterval = 60
    public init() {}

    public func issue(_ path: String) -> String {
        let n = ControlServer.newToken()
        q.lock(); issued[n] = (path, Date().addingTimeInterval(ttl)); q.unlock()
        return n
    }

    /// true once, when `nonce` was issued for `path` and has not expired
    public func check(_ nonce: String, path: String) -> Bool {
        q.lock(); defer { q.unlock() }
        guard let g = issued.removeValue(forKey: nonce) else { return false }
        return g.path == path && g.until > Date()
    }
}
