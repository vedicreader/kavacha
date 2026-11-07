import Foundation

/// The folders and files the app keeps outside its bundle. See contract/api-1.md.
public struct Paths: Sendable, Equatable {
    /// ~/Library/Application Support/<support>
    public let support: URL
    /// ~/Library/Caches/<support>
    public let caches: URL
    /// the env marker and the server's console script
    public let markerName: String, serverName: String

    public init(support: URL, caches: URL, config: LauncherConfig = Kavacha.config) {
        self.support = support; self.caches = caches; self.markerName = config.marker; self.serverName = config.server
    }

    public static func user(_ c: LauncherConfig = Kavacha.config) -> Paths {
        let fm = FileManager.default
        return Paths(support: fm.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appending(path: c.support),
                     caches: fm.urls(for: .cachesDirectory, in: .userDomainMask)[0].appending(path: c.support), config: c)
    }

    public var locks: URL { support.appending(path: "locks") }
    public func lock(_ n: Int) -> URL { locks.appending(path: String(n)) }
    public var envs: URL { support.appending(path: "envs") }
    /// one env per lock hash; the folder name is the first 16 hex characters
    public func env(_ hash: String) -> URL { envs.appending(path: String(hash.prefix(16))) }
    public func marker(_ hash: String) -> URL { env(hash).appending(path: markerName) }
    public var python: URL { support.appending(path: "python") }
    public var state: URL { support.appending(path: "state.json") }
    public var logs: URL { support.appending(path: "logs") }
    public func syncLog(_ hash: String) -> URL { logs.appending(path: "sync-\(hash.prefix(16)).log") }
    public var serverLog: URL { logs.appending(path: "server.log") }
    public var runLock: URL { support.appending(path: "run.lock") }
    public var uvCache: URL { caches.appending(path: "uv") }
    public func server(_ hash: String) -> URL { env(hash).appending(path: "bin/\(serverName)") }
}
