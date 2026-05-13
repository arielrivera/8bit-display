import CoreBluetooth
import Foundation

let serviceUUID = CBUUID(string: "0000ffd0-0000-1000-8000-00805f9b34fb")
let writeUUID = CBUUID(string: "0000ffd1-0000-1000-8000-00805f9b34fb")

func readArgument(_ name: String, default defaultValue: String? = nil) -> String? {
    let args = CommandLine.arguments
    guard let index = args.firstIndex(of: name), args.indices.contains(index + 1) else {
        return defaultValue
    }
    return args[index + 1]
}

func parseHex(_ line: String) -> Data? {
    let clean = line.replacingOccurrences(of: " ", with: "").trimmingCharacters(in: .whitespacesAndNewlines)
    guard !clean.isEmpty, clean.count % 2 == 0 else { return nil }

    var bytes: [UInt8] = []
    var index = clean.startIndex
    while index < clean.endIndex {
        let next = clean.index(index, offsetBy: 2)
        guard let byte = UInt8(clean[index..<next], radix: 16) else { return nil }
        bytes.append(byte)
        index = next
    }
    return Data(bytes)
}

func loadPackets(path: String) throws -> [Data] {
    let text = try String(contentsOfFile: path, encoding: .utf8)
    return text.split(separator: "\n").compactMap { parseHex(String($0)) }
}

final class BLEPacketWriter: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    private var manager: CBCentralManager!
    private var targetPeripheral: CBPeripheral?
    private let targetName: String
    private let packets: [Data]
    private let dryRun: Bool
    private let delaySeconds: Double

    init(targetName: String, packets: [Data], dryRun: Bool, delaySeconds: Double) {
        self.targetName = targetName
        self.packets = packets
        self.dryRun = dryRun
        self.delaySeconds = delaySeconds
        super.init()
        manager = CBCentralManager(delegate: self, queue: nil)
    }

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        guard central.state == .poweredOn else {
            print("Bluetooth state is \(central.state.rawValue); waiting...")
            return
        }
        print("Scanning for \(targetName)...")
        central.scanForPeripherals(withServices: [serviceUUID], options: nil)
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral, advertisementData: [String: Any], rssi RSSI: NSNumber) {
        let name = peripheral.name ?? advertisementData[CBAdvertisementDataLocalNameKey] as? String ?? ""
        print("Found \(name.isEmpty ? "<unknown>" : name) \(peripheral.identifier.uuidString)")
        guard name == targetName || name.contains("Matrix") else { return }

        targetPeripheral = peripheral
        peripheral.delegate = self
        central.stopScan()
        print("Connecting to \(name)...")
        central.connect(peripheral, options: nil)
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        print("Connected. Discovering service...")
        peripheral.discoverServices([serviceUUID])
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        if let error {
            finish("Service discovery failed: \(error)")
            return
        }
        guard let service = peripheral.services?.first(where: { $0.uuid == serviceUUID }) else {
            finish("Display service not found")
            return
        }
        peripheral.discoverCharacteristics([writeUUID], for: service)
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        if let error {
            finish("Characteristic discovery failed: \(error)")
            return
        }
        guard let characteristic = service.characteristics?.first(where: { $0.uuid == writeUUID }) else {
            finish("Write characteristic not found")
            return
        }

        if dryRun {
            for (index, packet) in packets.enumerated() {
                print(String(format: "%02d: %@", index + 1, packet.map { String(format: "%02x", $0) }.joined(separator: " ")))
            }
            finish("Dry run complete. Add --send to write.")
            return
        }

        Task { await sendPackets(peripheral: peripheral, characteristic: characteristic) }
    }

    private func sendPackets(peripheral: CBPeripheral, characteristic: CBCharacteristic) async {
        for (index, packet) in packets.enumerated() {
            peripheral.writeValue(packet, for: characteristic, type: .withoutResponse)
            print("Sent packet \(index + 1)/\(packets.count): \(packet.count) bytes")
            try? await Task.sleep(nanoseconds: UInt64(delaySeconds * 1_000_000_000))
        }
        finish("Done")
    }

    private func finish(_ message: String) {
        print(message)
        if let peripheral = targetPeripheral {
            manager.cancelPeripheralConnection(peripheral)
        }
        CFRunLoopStop(CFRunLoopGetMain())
    }
}

guard let packetPath = readArgument("--packets") else {
    print("Usage: swift swift/BLEWritePackets.swift --packets packets.hex [--send] [--name \"MI Matrix Display\"]")
    exit(2)
}

let packets = try loadPackets(path: packetPath)
let dryRun = !CommandLine.arguments.contains("--send")
let targetName = readArgument("--name", default: "MI Matrix Display")!
let delay = Double(readArgument("--delay", default: "0.05")!) ?? 0.05

_ = BLEPacketWriter(targetName: targetName, packets: packets, dryRun: dryRun, delaySeconds: delay)
CFRunLoopRun()

