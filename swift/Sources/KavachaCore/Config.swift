import Foundation

/// kavacha.json: every name the launcher uses, written by `kavacha.thin.Thin.config`. See contract/api-1.md.
public struct LauncherConfig: Codable, Sendable, Equatable {
    public struct BridgeNames: Codable, Sendable, Equatable {
        public var handler: String
        public var flag: String
        public var methods: [String]
        public var js_global: String
    }
    public struct WindowSpec: Codable, Sendable, Equatable {
        public var size: [Double]
        public var min_size: [Double]
        public var home: String
        public var title_prefix: String
    }
    public struct Titlebar: Codable, Sendable, Equatable {
        /// `mac-unified` or `native`
        public var style: String
        public var query: String
        public var drag_class: String
        public var unified: Bool { style == "mac-unified" }
    }
    public var api: Int
    public var name: String
    public var identifier: String
    public var support: String
    public var marker: String
    public var sig_ns: String
    public var env_prefix: String
    public var server: String
    public var health: String
    public var lock_project: String
    public var python: String
    public var channel: String
    public var extras: [String]
    public var bridge: BridgeNames
    public var sites: [String: String]
    public var routes: [String: String]
    public var capabilities: [String]
    public var menus: String
    public var menu_action_js: String
    public var window: WindowSpec
    public var titlebar: Titlebar
    public var cask: String
    public var debug_env: String

    public enum Refusal: Error, Equatable { case newerAPI(Int) }

    /// the config in `url`; refused when it asks for a newer contract than this launcher's
    public static func load(_ url: URL) throws -> LauncherConfig {
        let c = try JSONDecoder().decode(LauncherConfig.self, from: Data(contentsOf: url))
        guard c.api <= LauncherAPI.version else { throw Refusal.newerAPI(c.api) }
        return c
    }

    /// the names an app called `name` gets when its spec gives no others, as `Thin` derives them
    public static func named(_ name: String, channel: String = "", extras: [String] = []) -> LauncherConfig {
        let low = name.lowercased()
        return LauncherConfig(api: LauncherAPI.version, name: name, identifier: "org.\(low).\(low)", support: name, marker: ".\(low)-env.json", sig_ns: "\(low)-lock",
                              env_prefix: name.uppercased() + "_", server: low, health: "/health", lock_project: "\(low)-lock", python: "3.13", channel: channel, extras: extras,
                              bridge: BridgeNames(handler: low, flag: "__\(low)", methods: ["open_folder", "pick_folder", "pick_path", "open_path", "recent", "set_background", "set_title", "titlebar"], js_global: "pywebview"),
                              sites: [:], routes: ["open": "/hub/open", "grant": "/hub/grant", "recent": "/app/recent"], capabilities: ["confirm", "grant", "update", "extras"],
                              menus: "/app/menu.json", menu_action_js: "leeAct({action})", window: WindowSpec(size: [1440, 900], min_size: [900, 560], home: "\(low):home", title_prefix: "\(low) — "),
                              titlebar: Titlebar(style: "native", query: "titlebar", drag_class: "pywebview-drag-region"), cask: low, debug_env: name.uppercased() + "_WEBVIEW_DEBUG")
    }

    public func route(_ k: String) -> String { routes[k] ?? "" }
    public func env(_ k: String) -> String { env_prefix + k }
}

/// The one config of this process: the launcher sets it from its bundle before anything else runs.
public enum Kavacha {
    nonisolated(unsafe) public static var config = LauncherConfig.named("App")
}
