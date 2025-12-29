import SwiftUI

// MARK: - Data Models

public struct OctopusData: Codable, Sendable {
    var timestamp: String?
    var livePowerWatts: Int?
    var rate: Double?
    var isOffPeak: Bool
    var rateEndsInSeconds: Int
    var balance: Double
    var balanceIsCredit: Bool
    var dispatchStatus: String
    var dispatchEnd: String?
    var nextDispatchStart: String?
    var nextDispatchEnd: String?
    var yesterdayKwh: Double
    var yesterdayCost: Double
    var todayKwh: Double
    var todayCost: Double
    var hourlyUsage: [Double]
    var liveHistory: [Int]
    var tariffName: String?
    var standingCharge: Double
    var hasSavingSession: Bool
    var savingSessionStart: String?
    var savingSessionEnd: String?
    var savingSessionActive: Bool
    var error: String?
    var response: String?
    // New computed fields
    var offPeakStart: String?
    var offPeakEnd: String?
    var offPeakPercentage: Double
    var monthlyProjection: Double
    var peakRate: Double?
    var offPeakRate: Double?

    enum CodingKeys: String, CodingKey {
        case timestamp, rate, balance, error, response
        case livePowerWatts = "live_power_watts"
        case isOffPeak = "is_off_peak"
        case rateEndsInSeconds = "rate_ends_in_seconds"
        case balanceIsCredit = "balance_is_credit"
        case dispatchStatus = "dispatch_status"
        case dispatchEnd = "dispatch_end"
        case nextDispatchStart = "next_dispatch_start"
        case nextDispatchEnd = "next_dispatch_end"
        case yesterdayKwh = "yesterday_kwh"
        case yesterdayCost = "yesterday_cost"
        case todayKwh = "today_kwh"
        case todayCost = "today_cost"
        case hourlyUsage = "hourly_usage"
        case liveHistory = "live_history"
        case tariffName = "tariff_name"
        case standingCharge = "standing_charge"
        case hasSavingSession = "has_saving_session"
        case savingSessionStart = "saving_session_start"
        case savingSessionEnd = "saving_session_end"
        case savingSessionActive = "saving_session_active"
        case offPeakStart = "off_peak_start"
        case offPeakEnd = "off_peak_end"
        case offPeakPercentage = "off_peak_percentage"
        case monthlyProjection = "monthly_projection"
        case peakRate = "peak_rate"
        case offPeakRate = "off_peak_rate"
    }

    init() {
        isOffPeak = false
        rateEndsInSeconds = 0
        balance = 0
        balanceIsCredit = false
        dispatchStatus = "none"
        yesterdayKwh = 0
        yesterdayCost = 0
        todayKwh = 0
        todayCost = 0
        hourlyUsage = []
        liveHistory = []
        standingCharge = 0
        hasSavingSession = false
        savingSessionActive = false
        offPeakPercentage = 0
        monthlyProjection = 0
    }
}

// MARK: - App State

@MainActor
public class AppState: ObservableObject {
    @Published public var data = OctopusData()
    @Published public var isLoading = true
    @Published public var lastError: String?
    @Published public var aiQuery = ""
    @Published public var aiResponse: String?
    @Published public var isAskingAI = false

    private var pythonBridge: PythonBridge?
    private var refreshTimer: Timer?

    public var menuBarTitle: String {
        // Show charging icon when car is dispatching
        let prefix = data.dispatchStatus == "charging" ? "🔌 " : ""

        // Priority: live power > rate > fallback icon
        if let watts = data.livePowerWatts {
            let power = watts >= 1000 ? String(format: "%.1fkW", Double(watts)/1000) : "\(watts)W"
            return prefix + power
        }
        if let rate = data.rate {
            return prefix + String(format: "%.0fp", rate)
        }
        return prefix.isEmpty ? "⚡" : "🔌"
    }

    public init() {
        Task { @MainActor in
            self.setupBridge()
            self.startAutoRefresh()
        }
    }

    private func setupBridge() {
        pythonBridge = PythonBridge { [weak self] data in
            Task { @MainActor in self?.handleData(data) }
        }
        pythonBridge?.start()
    }

    private func startAutoRefresh() {
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refresh() }
        }
    }

    private func handleData(_ newData: OctopusData) {
        isLoading = false
        lastError = newData.error

        if let response = newData.response {
            aiResponse = response
            isAskingAI = false
            return
        }

        if newData.error == nil {
            data = newData
        }
    }

    public func askAI(_ question: String) {
        guard !question.isEmpty else { return }
        isAskingAI = true
        aiResponse = nil
        pythonBridge?.sendCommand(["command": "ask", "question": question])
    }

    public func refresh() {
        isLoading = true
        pythonBridge?.sendCommand(["command": "refresh"])
    }

    public func quit() {
        refreshTimer?.invalidate()
        pythonBridge?.stop()
        NSApplication.shared.terminate(nil)
    }
}

// MARK: - Python Bridge

public final class PythonBridge: @unchecked Sendable {
    private var process: Process?
    private var outputPipe: Pipe?
    private var inputPipe: Pipe?
    private let onData: @Sendable (OctopusData) -> Void

    public init(onData: @escaping @Sendable (OctopusData) -> Void) {
        self.onData = onData
    }

    public func start() {
        process = Process()
        outputPipe = Pipe()
        inputPipe = Pipe()

        let serverPath = findServerPath()
        process?.executableURL = URL(fileURLWithPath: serverPath)
        process?.arguments = []
        process?.standardOutput = outputPipe
        process?.standardInput = inputPipe
        process?.standardError = FileHandle.nullDevice

        var env = ProcessInfo.processInfo.environment
        let envFile = NSHomeDirectory() + "/.octopus.env"
        if let contents = try? String(contentsOfFile: envFile, encoding: .utf8) {
            for line in contents.components(separatedBy: .newlines) {
                let trimmed = line.trimmingCharacters(in: .whitespaces)
                guard !trimmed.isEmpty, !trimmed.hasPrefix("#") else { continue }
                let parts = trimmed.split(separator: "=", maxSplits: 1)
                if parts.count == 2 {
                    env[String(parts[0]).trimmingCharacters(in: .whitespaces)] =
                        String(parts[1]).trimmingCharacters(in: .whitespaces)
                }
            }
        }
        process?.environment = env

        let handler = self.onData
        outputPipe?.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            if !data.isEmpty { Self.processOutput(data, handler: handler) }
        }

        try? process?.run()
    }

    private static func processOutput(_ data: Data, handler: @escaping @Sendable (OctopusData) -> Void) {
        guard let string = String(data: data, encoding: .utf8) else { return }
        for line in string.components(separatedBy: .newlines) where !line.isEmpty {
            if let octopusData = try? JSONDecoder().decode(OctopusData.self, from: Data(line.utf8)) {
                handler(octopusData)
            }
        }
    }

    private func findServerPath() -> String {
        let paths = [
            "/Library/Frameworks/Python.framework/Versions/3.12/bin/octopus-server",
            "/opt/homebrew/bin/octopus-server",
            "/usr/local/bin/octopus-server",
            "\(NSHomeDirectory())/.local/bin/octopus-server"
        ]
        return paths.first { FileManager.default.fileExists(atPath: $0) } ?? "octopus-server"
    }

    public func sendCommand(_ command: [String: Any]) {
        guard let inputPipe = inputPipe,
              let data = try? JSONSerialization.data(withJSONObject: command) else { return }
        inputPipe.fileHandleForWriting.write(data)
        inputPipe.fileHandleForWriting.write("\n".data(using: .utf8)!)
    }

    public func stop() {
        sendCommand(["command": "quit"])
        process?.terminate()
    }
}

// MARK: - Reusable Components

struct CardView<Content: View>: View {
    let icon: String
    let title: String
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(title, systemImage: icon)
                .font(.system(size: 10, weight: .semibold))
                .foregroundColor(.secondary)
            content()
        }
        .padding(10)
        .background(Color.primary.opacity(0.04))
        .cornerRadius(8)
        .padding(.horizontal, 10)
    }
}

struct RateProgressBar: View {
    let progress: Double
    let isOffPeak: Bool

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 2)
                    .fill(Color.secondary.opacity(0.15))
                RoundedRectangle(cornerRadius: 2)
                    .fill(isOffPeak ? Color.cyan : Color.orange)
                    .frame(width: geo.size.width * min(max(progress, 0), 1))
            }
        }
        .frame(height: 4)
    }
}

struct QuickButton: View {
    let text: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(text)
                .font(.system(size: 9))
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.primary.opacity(0.06))
                .cornerRadius(4)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Menu Bar View

public struct MenuBarView: View {
    @EnvironmentObject var state: AppState

    public init() {}

    public var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            if state.isLoading && state.data.rate == nil {
                loadingView
            } else if let error = state.lastError {
                errorView(error)
            } else {
                heroSection
                ScrollView(.vertical, showsIndicators: false) {
                    VStack(spacing: 8) {
                        rateCard
                        if state.data.dispatchStatus != "none" {
                            chargingCard
                        }
                        if state.data.savingSessionActive || state.data.hasSavingSession {
                            savingSessionCard
                        }
                        usageCard
                        insightsCard
                        aiCard
                    }
                    .padding(.vertical, 8)
                }
                Divider()
                footer
            }
        }
        .frame(width: 300, height: 650)
        .background(Color(NSColor.windowBackgroundColor))
    }

    // MARK: - Hero Section

    private var heroSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top) {
                // Live power or rate
                VStack(alignment: .leading, spacing: 2) {
                    if let watts = state.data.livePowerWatts {
                        HStack(spacing: 4) {
                            Image(systemName: "bolt.fill")
                                .foregroundColor(.orange)
                            Text(formatPower(watts))
                                .font(.system(size: 22, weight: .semibold, design: .rounded))
                        }
                        if let rate = state.data.rate {
                            Text("\(formatCostPerHour(watts, rate: rate))")
                                .font(.system(size: 11))
                                .foregroundColor(.secondary)
                        }
                    } else if let rate = state.data.rate {
                        HStack(spacing: 4) {
                            Image(systemName: state.data.isOffPeak ? "moon.fill" : "sun.max.fill")
                                .foregroundColor(state.data.isOffPeak ? .cyan : .orange)
                            Text(String(format: "%.1fp", rate))
                                .font(.system(size: 22, weight: .semibold, design: .rounded))
                        }
                        Text(state.data.isOffPeak ? "Off-peak rate" : "Peak rate")
                            .font(.system(size: 11))
                            .foregroundColor(.secondary)
                    }
                }

                Spacer()

                // Balance
                VStack(alignment: .trailing, spacing: 2) {
                    Text(formatBalance(state.data.balance, credit: state.data.balanceIsCredit))
                        .font(.system(size: 16, weight: .semibold, design: .monospaced))
                        .foregroundColor(state.data.balanceIsCredit ? .green : .primary)
                    Text("Balance")
                        .font(.system(size: 10))
                        .foregroundColor(.secondary)
                }
            }

            // Rate progress bar
            VStack(alignment: .leading, spacing: 4) {
                RateProgressBar(
                    progress: calculateRateProgress(),
                    isOffPeak: state.data.isOffPeak
                )

                HStack {
                    Text(String(format: "%.1fp", state.data.rate ?? 0))
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundColor(state.data.isOffPeak ? .cyan : .orange)

                    Image(systemName: "arrow.right")
                        .font(.system(size: 8))
                        .foregroundColor(.secondary)

                    Text(String(format: "%.1fp", state.data.isOffPeak ? (state.data.peakRate ?? 0) : (state.data.offPeakRate ?? 0)))
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundColor(.secondary)

                    Spacer()

                    Text("in \(formatTimeRemaining(state.data.rateEndsInSeconds))")
                        .font(.system(size: 9))
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding(12)
        .background(Color.primary.opacity(0.02))
    }

    // MARK: - Rate Card

    private var rateCard: some View {
        CardView(icon: "chart.bar.fill", title: "RATES") {
            VStack(alignment: .leading, spacing: 6) {
                // Peak rate row
                HStack {
                    Circle()
                        .fill(!state.data.isOffPeak ? Color.orange : Color.secondary.opacity(0.3))
                        .frame(width: 6, height: 6)
                    Text("Peak")
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                    Spacer()
                    Text(String(format: "%.1fp", state.data.peakRate ?? state.data.rate ?? 0))
                        .font(.system(size: 11, weight: .medium, design: .monospaced))
                    Text("05:30–23:30")
                        .font(.system(size: 9))
                        .foregroundColor(.secondary)
                }

                // Off-peak rate row
                HStack {
                    Circle()
                        .fill(state.data.isOffPeak ? Color.cyan : Color.secondary.opacity(0.3))
                        .frame(width: 6, height: 6)
                    Text("Off-peak")
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                    Spacer()
                    Text(String(format: "%.1fp", state.data.offPeakRate ?? 7.0))
                        .font(.system(size: 11, weight: .medium, design: .monospaced))
                    Text("23:30–05:30")
                        .font(.system(size: 9))
                        .foregroundColor(.secondary)
                }

                // Standing charge
                HStack {
                    Text("Standing charge")
                        .font(.system(size: 10))
                        .foregroundColor(.secondary)
                    Spacer()
                    Text(String(format: "%.2fp/day", state.data.standingCharge))
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(.secondary)
                }
                .padding(.top, 4)
            }
        }
    }

    // MARK: - Charging Card

    private var chargingCard: some View {
        let isCharging = state.data.dispatchStatus == "charging"
        let goldColor = Color(red: 1.0, green: 0.84, blue: 0.0)

        return VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 4) {
                Image(systemName: "ev.charger.fill")
                    .foregroundColor(isCharging ? goldColor : .secondary)
                Text("SMART CHARGING")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundColor(isCharging ? goldColor : .secondary)
            }

            VStack(alignment: .leading, spacing: 6) {
                if isCharging {
                    HStack {
                        HStack(spacing: 4) {
                            Circle()
                                .fill(goldColor)
                                .frame(width: 6, height: 6)
                            Text("Charging")
                                .font(.system(size: 11, weight: .medium))
                                .foregroundColor(goldColor)
                        }
                        Spacer()
                        Text("until \(formatTime(state.data.dispatchEnd))")
                            .font(.system(size: 11))
                            .foregroundColor(.secondary)
                    }

                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 2)
                                .fill(Color.secondary.opacity(0.15))
                            RoundedRectangle(cornerRadius: 2)
                                .fill(goldColor)
                                .frame(width: geo.size.width * 0.6)
                        }
                    }
                    .frame(height: 4)
                } else if let start = state.data.nextDispatchStart {
                    HStack {
                        Text("Scheduled")
                            .font(.system(size: 11))
                            .foregroundColor(.secondary)
                        Spacer()
                        Text("\(formatTime(start)) → \(formatTime(state.data.nextDispatchEnd))")
                            .font(.system(size: 11, design: .monospaced))
                    }
                }
            }
        }
        .padding(10)
        .background(isCharging ? goldColor.opacity(0.08) : Color.primary.opacity(0.04))
        .cornerRadius(8)
        .padding(.horizontal, 10)
    }

    // MARK: - Saving Session Card

    private var savingSessionCard: some View {
        CardView(icon: "bolt.badge.clock.fill", title: "SAVING SESSION") {
            HStack {
                if state.data.savingSessionActive {
                    Text("LIVE")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundColor(.purple)
                    Spacer()
                    Text("ends \(formatTime(state.data.savingSessionEnd))")
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                } else if let start = state.data.savingSessionStart {
                    Text("Upcoming")
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                    Spacer()
                    Text(formatTime(start))
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundColor(.purple)
                }
            }
        }
    }

    // MARK: - Usage Card

    private var usageCard: some View {
        CardView(icon: "chart.line.uptrend.xyaxis", title: "USAGE") {
            VStack(alignment: .leading, spacing: 8) {
                // Today
                HStack {
                    Text("Today")
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                    Spacer()
                    Text(formatKwh(state.data.todayKwh))
                        .font(.system(size: 11, weight: .medium, design: .monospaced))
                    Text(formatCost(state.data.todayCost))
                        .font(.system(size: 10))
                        .foregroundColor(.secondary)

                    // Change indicator
                    if state.data.yesterdayKwh > 0 && state.data.todayKwh > 0 {
                        let change = ((state.data.todayKwh / state.data.yesterdayKwh) - 1) * 100
                        Text(String(format: "%@%.0f%%", change >= 0 ? "+" : "", change))
                            .font(.system(size: 9, weight: .medium))
                            .foregroundColor(change < 0 ? .green : .orange)
                    }
                }

                // Yesterday
                HStack {
                    Text("Yesterday")
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                    Spacer()
                    Text(formatKwh(state.data.yesterdayKwh))
                        .font(.system(size: 11, weight: .medium, design: .monospaced))
                    Text(formatCost(state.data.yesterdayCost))
                        .font(.system(size: 10))
                        .foregroundColor(.secondary)
                }

                // Sparkline with labels
                if !state.data.hourlyUsage.isEmpty {
                    VStack(spacing: 2) {
                        sparkline
                        HStack {
                            Text("0h")
                            Spacer()
                            Text("12h")
                            Spacer()
                            Text("Now")
                        }
                        .font(.system(size: 8))
                        .foregroundColor(.secondary)
                    }
                    .padding(.top, 4)
                }
            }
        }
    }

    private var sparkline: some View {
        let values = state.data.hourlyUsage
        let max = values.max() ?? 1
        let currentHour = Calendar.current.component(.hour, from: Date())

        return HStack(alignment: .bottom, spacing: 1) {
            ForEach(Array(values.enumerated()), id: \.offset) { index, value in
                let hourIndex = (currentHour - values.count + index + 25) % 24
                let isOffPeakHour = hourIndex < 6 || hourIndex == 23

                RoundedRectangle(cornerRadius: 1)
                    .fill(isOffPeakHour ? Color.cyan.opacity(0.6) : Color.secondary.opacity(0.4))
                    .frame(height: max > 0 ? CGFloat(value / max) * 28 + 2 : 2)
            }
        }
        .frame(height: 32)
    }

    // MARK: - Insights Card

    private var insightsCard: some View {
        CardView(icon: "lightbulb.fill", title: "INSIGHTS") {
            VStack(alignment: .leading, spacing: 6) {
                // Rate comparison
                if let peak = state.data.peakRate, let offPeak = state.data.offPeakRate {
                    HStack(spacing: 4) {
                        Image(systemName: "bolt.fill")
                            .font(.system(size: 10))
                            .foregroundColor(.orange)
                        Text("Peak \(String(format: "%.1fp", peak))")
                            .font(.system(size: 11))
                        Text("→")
                            .foregroundColor(.secondary)
                        Text("Off-peak \(String(format: "%.1fp", offPeak))")
                            .font(.system(size: 11))
                            .foregroundColor(.cyan)
                        Text("(\(Int((1 - offPeak/peak) * 100))% cheaper)")
                            .font(.system(size: 10))
                            .foregroundColor(.green)
                    }
                }

                // Off-peak window
                if let start = state.data.offPeakStart, let end = state.data.offPeakEnd {
                    HStack(spacing: 4) {
                        Image(systemName: "moon.fill")
                            .font(.system(size: 10))
                            .foregroundColor(.cyan)
                        Text("Off-peak: \(start) → \(end)")
                            .font(.system(size: 11))
                    }
                }

                // Off-peak percentage
                if state.data.offPeakPercentage > 0 {
                    HStack(spacing: 4) {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 10))
                            .foregroundColor(.green)
                        Text("\(Int(state.data.offPeakPercentage))% of today at off-peak rates")
                            .font(.system(size: 11))
                    }
                }

                // Daily standing charge
                if state.data.standingCharge > 0 {
                    HStack(spacing: 4) {
                        Image(systemName: "house.fill")
                            .font(.system(size: 10))
                            .foregroundColor(.secondary)
                        Text(String(format: "Standing charge: %.1fp/day", state.data.standingCharge))
                            .font(.system(size: 11))
                            .foregroundColor(.secondary)
                    }
                }

                // Monthly projection
                if state.data.monthlyProjection > 0 {
                    HStack(spacing: 4) {
                        Image(systemName: "calendar")
                            .font(.system(size: 10))
                            .foregroundColor(.purple)
                        Text(String(format: "On track for £%.0f/month", state.data.monthlyProjection))
                            .font(.system(size: 11, weight: .medium))
                    }
                }

                // Estimated savings (rough calculation)
                if state.data.yesterdayCost > 0 {
                    let standardRate = 24.5  // Average standard rate
                    let savingsEstimate = (state.data.yesterdayKwh * standardRate / 100) - state.data.yesterdayCost
                    if savingsEstimate > 0 {
                        HStack(spacing: 4) {
                            Image(systemName: "arrow.down.circle.fill")
                                .font(.system(size: 10))
                                .foregroundColor(.green)
                            Text(String(format: "Saved ~£%.2f yesterday vs standard", savingsEstimate))
                                .font(.system(size: 11))
                                .foregroundColor(.green)
                        }
                    }
                }
            }
        }
    }

    // MARK: - AI Card

    private var aiCard: some View {
        CardView(icon: "sparkles", title: "ASK") {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 6) {
                    TextField("Ask about your energy...", text: $state.aiQuery)
                        .textFieldStyle(.plain)
                        .font(.system(size: 11))
                        .padding(.horizontal, 8)
                        .padding(.vertical, 6)
                        .background(Color(NSColor.textBackgroundColor))
                        .cornerRadius(6)
                        .onSubmit { submitAI() }

                    Button(action: submitAI) {
                        if state.isAskingAI {
                            ProgressView()
                                .scaleEffect(0.5)
                                .frame(width: 20, height: 20)
                        } else {
                            Image(systemName: "arrow.up.circle.fill")
                                .font(.system(size: 16))
                                .foregroundColor(.accentColor)
                        }
                    }
                    .buttonStyle(.plain)
                    .disabled(state.aiQuery.isEmpty || state.isAskingAI)
                }

                // Quick action buttons
                HStack(spacing: 6) {
                    QuickButton(text: "Best time?") {
                        state.aiQuery = "When is the best time to use energy today?"
                        submitAI()
                    }
                    QuickButton(text: "This week?") {
                        state.aiQuery = "How much did I spend this week?"
                        submitAI()
                    }
                    QuickButton(text: "Compare") {
                        state.aiQuery = "How does today compare to yesterday?"
                        submitAI()
                    }
                }

                if let response = state.aiResponse {
                    Text(markdownToAttributed(response))
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                        .textSelection(.enabled)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.top, 4)
                }
            }
        }
    }

    private func submitAI() {
        let query = state.aiQuery
        state.aiQuery = ""
        state.askAI(query)
    }

    // MARK: - Footer

    private var footer: some View {
        HStack(spacing: 8) {
            Button(action: { state.refresh() }) {
                HStack(spacing: 4) {
                    Image(systemName: "arrow.clockwise")
                        .font(.system(size: 10))
                    Text(formatLastUpdated())
                        .font(.system(size: 9))
                        .foregroundColor(.secondary)
                }
            }
            .buttonStyle(.plain)
            .opacity(state.isLoading ? 0.5 : 1)

            Spacer()

            // Branding + tariff
            HStack(spacing: 4) {
                Button(action: { NSWorkspace.shared.open(URL(string: "https://github.com/abracadabra50/open-octopus")!) }) {
                    HStack(spacing: 2) {
                        Text("🐙")
                            .font(.system(size: 10))
                        Text("Open Octopus")
                            .font(.system(size: 9, weight: .medium))
                            .foregroundColor(.secondary)
                    }
                }
                .buttonStyle(.plain)
                if let tariff = state.data.tariffName {
                    Text("·")
                        .foregroundColor(.secondary)
                    Text(formatTariffName(tariff))
                        .font(.system(size: 9))
                        .foregroundColor(.secondary)
                }
            }

            Spacer()

            Button(action: { NSWorkspace.shared.open(URL(string: "https://octopus.energy/dashboard/")!) }) {
                Image(systemName: "arrow.up.right.square")
                    .font(.system(size: 11))
            }
            .buttonStyle(.plain)

            Button(action: { state.quit() }) {
                Image(systemName: "xmark")
                    .font(.system(size: 10))
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }

    // MARK: - Loading & Error Views

    private var loadingView: some View {
        VStack(spacing: 12) {
            Spacer()
            ProgressView()
                .scaleEffect(0.8)
            Text("Loading...")
                .font(.system(size: 11))
                .foregroundColor(.secondary)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func errorView(_ error: String) -> some View {
        VStack(spacing: 12) {
            Spacer()
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 24))
                .foregroundColor(.orange)
            Text(error)
                .font(.system(size: 11))
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            Button("Retry") { state.refresh() }
                .buttonStyle(.borderedProminent)
                .controlSize(.small)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Formatters

    private func formatBalance(_ amount: Double, credit: Bool) -> String {
        let formatted = String(format: "£%.2f", amount)
        return credit ? "+\(formatted)" : formatted
    }

    private func formatPower(_ watts: Int) -> String {
        watts >= 1000 ? String(format: "%.1fkW", Double(watts)/1000) : "\(watts)W"
    }

    private func formatCostPerHour(_ watts: Int, rate: Double) -> String {
        let cost = (Double(watts) / 1000) * rate
        return String(format: "%.1fp/h", cost)
    }

    private func formatTimeRemaining(_ seconds: Int) -> String {
        let h = seconds / 3600
        let m = (seconds % 3600) / 60
        return h > 0 ? "\(h)h \(m)m" : "\(m)m"
    }

    private func formatKwh(_ kwh: Double) -> String {
        String(format: "%.1f kWh", kwh)
    }

    private func formatCost(_ cost: Double) -> String {
        String(format: "£%.2f", cost)
    }

    private func formatTime(_ iso: String?) -> String {
        guard let iso = iso else { return "-" }
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: iso) else { return "-" }
        let tf = DateFormatter()
        tf.dateFormat = "HH:mm"
        return tf.string(from: date)
    }

    private func formatLastUpdated() -> String {
        guard let timestamp = state.data.timestamp else { return "now" }
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: timestamp) else { return "now" }
        let seconds = Int(Date().timeIntervalSince(date))
        if seconds < 60 { return "now" }
        let minutes = seconds / 60
        return "\(minutes)m ago"
    }

    private func markdownToAttributed(_ text: String) -> AttributedString {
        do {
            return try AttributedString(
                markdown: text,
                options: AttributedString.MarkdownParsingOptions(
                    interpretedSyntax: .inlineOnlyPreservingWhitespace
                )
            )
        } catch {
            return AttributedString(text)
        }
    }

    private func formatTariffName(_ name: String) -> String {
        // Shorten tariff names like "INTELLI-VAR-24-10-29" to "INTELLI-VAR"
        let parts = name.split(separator: "-")
        if parts.count >= 2 {
            return parts.prefix(2).joined(separator: "-")
        }
        return name
    }

    private func calculateRateProgress() -> Double {
        // Estimate progress through current rate period
        // For a 30-min period, calculate how far through we are
        let totalSeconds = 1800.0  // 30 minutes typical for Agile
        let elapsed = totalSeconds - Double(state.data.rateEndsInSeconds)
        return max(0, min(1, elapsed / totalSeconds))
    }
}
