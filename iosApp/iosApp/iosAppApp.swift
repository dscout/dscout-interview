import SwiftUI
import Shared

@main
struct iosAppApp: App {
    init() {
        let baseUrl = Bundle.main.object(forInfoDictionaryKey: "BackendBaseURL") as! String
        BackendConfig.shared.configure(baseUrl: baseUrl)
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
