import CoreBluetooth
import Foundation

let serviceUUID = CBUUID(string: "0000ffd0-0000-1000-8000-00805f9b34fb")
let writeUUID = CBUUID(string: "0000ffd1-0000-1000-8000-00805f9b34fb")

func checksum(_ bytes: [UInt8]) -> UInt8 {
    bytes.reduce(UInt8(0)) { partial, byte in partial &+ byte }
}

func packet(_ message: [UInt8]) -> Data {
    var out: [UInt8] = [0xbc]
    out.append(contentsOf: message)
    out.append(checksum(message))
    if (message.count + 13) % 32 != 0 {
        out.append(0x55)
    }
    return Data(out)
}

func gammaCorrect(_ value: UInt8, gamma: Double = 0.6) -> UInt8 {
    let normalized = Double(value) / 255.0
    let corrected = pow(normalized, 1.0 / gamma)
    return UInt8(max(0, min(255, Int(round(corrected * 255.0)))))
}

func imagePackets() -> [Data] {
    var pixels: [(UInt8, UInt8, UInt8)] = []
    for y in 0..<16 {
        for x in 0..<16 {
            pixels.append((UInt8(x * 17), UInt8(y * 17), UInt8(((x + y) / 2) * 17)))
        }
    }

    var packets: [Data] = [packet([0x0f, 0xf1, 0x08])]
    for chunk in 0..<8 {
        var body: [UInt8] = [0x0f, UInt8(chunk + 1)]
        let start = chunk * 32
        for pixel in pixels[start..<(start + 32)] {
            body.append(gammaCorrect(pixel.0))
            body.append(gammaCorrect(pixel.1))
            body.append(gammaCorrect(pixel.2))
        }
        packets.append(packet(body))
    }
    packets.append(packet([0x0f, 0xf2, 0x08]))
    return packets
}

final class BLEDisplayWriter: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    private var manager: CBCentralManager!
    private var targetPeripheral: CBPeripheral?
    private var writeCharacteristic: CBCharacteristic?
    private let targetName: String
    private let packets: [Data]
    private let dryRun: Bool

    init(targetName: String, packets: [Data], dryRun: Bool) {
        self.targetName = targetName
        self.packets = packets
        self.dryRun = dryRun
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
        writeCharacteristic = characteristic

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
            try? await Task.sleep(nanoseconds: 50_000_000)
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

let args = CommandLine.arguments
let dryRun = !args.contains("--send")
let nameIndex = args.firstIndex(of: "--name")
let targetName = nameIndex.flatMap { args.indices.contains($0 + 1) ? args[$0 + 1] : nil } ?? "MI Matrix Display"

_ = BLEDisplayWriter(targetName: targetName, packets: imagePackets(), dryRun: dryRun)
CFRunLoopRun()

