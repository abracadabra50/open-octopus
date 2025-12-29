import SwiftUI
import OctopusMenuBarFeature

@main
struct OctopusMenuBarApp: App {
    @StateObject private var appState: AppState

    init() {
        let state = AppState()
        _appState = StateObject(wrappedValue: state)
    }

    var body: some Scene {
        MenuBarExtra {
            MenuBarView()
                .environmentObject(appState)
        } label: {
            HStack(spacing: 4) {
                Image(systemName: "bolt.fill")
                if appState.menuBarTitle != "⚡" {
                    Text(appState.menuBarTitle)
                }
            }
        }
        .menuBarExtraStyle(.window)
    }
}
