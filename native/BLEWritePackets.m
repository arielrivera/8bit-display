#import <CoreBluetooth/CoreBluetooth.h>
#import <Foundation/Foundation.h>

static CBUUID *ServiceUUID(void) {
    return [CBUUID UUIDWithString:@"0000ffd0-0000-1000-8000-00805f9b34fb"];
}

static CBUUID *WriteUUID(void) {
    return [CBUUID UUIDWithString:@"0000ffd1-0000-1000-8000-00805f9b34fb"];
}

static CBUUID *NotifyUUID(void) {
    return [CBUUID UUIDWithString:@"0000ffd2-0000-1000-8000-00805f9b34fb"];
}

static CBUUID *NotifyDescriptorUUID(void) {
    return [CBUUID UUIDWithString:@"00002902-0000-1000-8000-00805f9b34fb"];
}

static NSData *ResetPacket(void) {
    static NSData *packet = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        const uint8_t bytes[] = { 0xbc, 0x00, 0x15, 0x15, 0x55 };
        packet = [NSData dataWithBytes:bytes length:sizeof(bytes)];
    });
    return packet;
}

static NSString *LogPath = nil;

static void LogLine(NSString *format, ...) {
    va_list args;
    va_start(args, format);
    NSString *message = [[NSString alloc] initWithFormat:format arguments:args];
    va_end(args);

    NSLog(@"%@", message);
    if (LogPath == nil) return;

    NSString *line = [message stringByAppendingString:@"\n"];
    NSData *data = [line dataUsingEncoding:NSUTF8StringEncoding];
    if (![[NSFileManager defaultManager] fileExistsAtPath:LogPath]) {
        [data writeToFile:LogPath atomically:YES];
        return;
    }

    NSFileHandle *handle = [NSFileHandle fileHandleForWritingAtPath:LogPath];
    [handle seekToEndOfFile];
    [handle writeData:data];
    [handle closeFile];
}

static NSString *ArgValue(NSArray<NSString *> *args, NSString *name, NSString *fallback) {
    NSUInteger index = [args indexOfObject:name];
    if (index == NSNotFound || index + 1 >= args.count) return fallback;
    return args[index + 1];
}

static NSData *DataFromHexLine(NSString *line) {
    NSString *clean = [[[line stringByReplacingOccurrencesOfString:@" " withString:@""]
        stringByReplacingOccurrencesOfString:@"\t" withString:@""]
        stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    if (clean.length == 0 || clean.length % 2 != 0) return nil;

    NSMutableData *data = [NSMutableData dataWithCapacity:clean.length / 2];
    for (NSUInteger i = 0; i < clean.length; i += 2) {
        NSString *byteString = [clean substringWithRange:NSMakeRange(i, 2)];
        unsigned int value = 0;
        if ([[NSScanner scannerWithString:byteString] scanHexInt:&value] == NO) return nil;
        uint8_t byte = (uint8_t)value;
        [data appendBytes:&byte length:1];
    }
    return data;
}

static NSArray<NSData *> *LoadPackets(NSString *path, NSError **error) {
    NSString *text = [NSString stringWithContentsOfFile:path encoding:NSUTF8StringEncoding error:error];
    if (text == nil) return nil;

    NSMutableArray<NSData *> *packets = [NSMutableArray array];
    for (NSString *line in [text componentsSeparatedByCharactersInSet:[NSCharacterSet newlineCharacterSet]]) {
        NSData *packet = DataFromHexLine(line);
        if (packet != nil) [packets addObject:packet];
    }
    return packets;
}

@interface BLEPacketWriter : NSObject <CBCentralManagerDelegate, CBPeripheralDelegate>
@property(nonatomic, strong) CBCentralManager *manager;
@property(nonatomic, strong) dispatch_queue_t managerQueue;
@property(nonatomic, strong) CBPeripheral *peripheral;
@property(nonatomic, strong) CBCharacteristic *writeCharacteristic;
@property(nonatomic, strong) CBCharacteristic *notifyCharacteristic;
@property(nonatomic, strong) NSArray<NSData *> *packets;
@property(nonatomic, copy) NSString *targetName;
@property(nonatomic, assign) BOOL shouldSend;
@property(nonatomic, assign) NSTimeInterval delay;
@property(nonatomic, assign) BOOL didFinish;
@property(nonatomic, assign) NSUInteger packetIndex;
@property(nonatomic, assign) BOOL sendStarted;
@property(nonatomic, assign) BOOL sendCompleted;
@property(nonatomic, assign) BOOL waitingForWriteReady;
@property(nonatomic, assign) BOOL didConnect;
@end

@implementation BLEPacketWriter

- (BOOL)nameMatches:(NSString *)name {
    if (name.length == 0) return NO;
    return [name isEqualToString:self.targetName] ||
        [name rangeOfString:@"Matrix" options:NSCaseInsensitiveSearch].location != NSNotFound ||
        [name rangeOfString:@"MIMatrix" options:NSCaseInsensitiveSearch].location != NSNotFound;
}

- (void)connectToPeripheral:(CBPeripheral *)peripheral name:(NSString *)name {
    self.peripheral = peripheral;
    peripheral.delegate = self;
    [self.manager stopScan];
    LogLine(@"Connecting to %@", name.length ? name : peripheral.identifier.UUIDString);
    [self.manager connectPeripheral:peripheral options:nil];
}

- (instancetype)initWithPackets:(NSArray<NSData *> *)packets
                     targetName:(NSString *)targetName
                     shouldSend:(BOOL)shouldSend
                          delay:(NSTimeInterval)delay {
    self = [super init];
    if (self) {
        _packets = packets;
        _targetName = targetName;
        _shouldSend = shouldSend;
        _delay = delay;
        _managerQueue = dispatch_queue_create("org.arielrivera.8bit-display.ble", DISPATCH_QUEUE_SERIAL);
        _manager = [[CBCentralManager alloc] initWithDelegate:self queue:_managerQueue];
        LogLine(@"Central manager initialized; initial state %ld", (long)_manager.state);
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(20 * NSEC_PER_SEC)), _managerQueue, ^{
            if (!self.didConnect) {
                [self finish:@"Timed out while scanning/connecting" code:1];
            }
        });
    }
    return self;
}

- (void)finish:(NSString *)message code:(int)code {
    if (self.didFinish) return;
    self.didFinish = YES;
    LogLine(@"%@", message);
    if (self.peripheral != nil) {
        [self.manager cancelPeripheralConnection:self.peripheral];
    }
    dispatch_async(dispatch_get_main_queue(), ^{
        exit(code);
    });
}

- (void)centralManagerDidUpdateState:(CBCentralManager *)central {
    if (central.state != CBManagerStatePoweredOn) {
        LogLine(@"Bluetooth state %ld; waiting", (long)central.state);
        return;
    }
    LogLine(@"Scanning for %@", self.targetName);
    NSArray<CBPeripheral *> *connected = [central retrieveConnectedPeripheralsWithServices:@[ ServiceUUID() ]];
    for (CBPeripheral *peripheral in connected) {
        NSString *name = peripheral.name ?: @"";
        LogLine(@"Already connected %@ %@", name.length ? name : @"<unknown>", peripheral.identifier.UUIDString);
        if ([self nameMatches:name] || connected.count == 1) {
            [self connectToPeripheral:peripheral name:name];
            return;
        }
    }
    [central scanForPeripheralsWithServices:nil options:@{ CBCentralManagerScanOptionAllowDuplicatesKey: @NO }];
}

- (void)centralManager:(CBCentralManager *)central
 didDiscoverPeripheral:(CBPeripheral *)peripheral
     advertisementData:(NSDictionary<NSString *,id> *)advertisementData
                  RSSI:(NSNumber *)RSSI {
    NSString *name = peripheral.name ?: advertisementData[CBAdvertisementDataLocalNameKey] ?: @"";
    LogLine(@"Found %@ %@", name.length ? name : @"<unknown>", peripheral.identifier.UUIDString);
    if (![self nameMatches:name]) return;

    [self connectToPeripheral:peripheral name:name];
}

- (void)centralManager:(CBCentralManager *)central didFailToConnectPeripheral:(CBPeripheral *)peripheral error:(NSError *)error {
    [self finish:[NSString stringWithFormat:@"Connect failed: %@", error] code:1];
}

- (void)centralManager:(CBCentralManager *)central didConnectPeripheral:(CBPeripheral *)peripheral {
    self.didConnect = YES;
    LogLine(@"Connected. Discovering service.");
    [peripheral discoverServices:@[ ServiceUUID() ]];
}

- (void)peripheral:(CBPeripheral *)peripheral didDiscoverServices:(NSError *)error {
    if (error != nil) {
        [self finish:[NSString stringWithFormat:@"Service discovery failed: %@", error] code:1];
        return;
    }
    for (CBService *service in peripheral.services) {
        if ([service.UUID isEqual:ServiceUUID()]) {
            [peripheral discoverCharacteristics:@[ WriteUUID(), NotifyUUID() ] forService:service];
            return;
        }
    }
    [self finish:@"Display service not found" code:1];
}

- (void)peripheral:(CBPeripheral *)peripheral
didDiscoverCharacteristicsForService:(CBService *)service
             error:(NSError *)error {
    if (error != nil) {
        [self finish:[NSString stringWithFormat:@"Characteristic discovery failed: %@", error] code:1];
        return;
    }

    CBCharacteristic *writeCharacteristic = nil;
    CBCharacteristic *notifyCharacteristic = nil;
    for (CBCharacteristic *characteristic in service.characteristics) {
        if ([characteristic.UUID isEqual:WriteUUID()]) {
            writeCharacteristic = characteristic;
        } else if ([characteristic.UUID isEqual:NotifyUUID()]) {
            notifyCharacteristic = characteristic;
        }
    }
    if (writeCharacteristic == nil) {
        [self finish:@"Write characteristic not found" code:1];
        return;
    }
    self.writeCharacteristic = writeCharacteristic;
    LogLine(
        @"Write characteristic ready; max write without response %lu bytes; can send now: %@",
        (unsigned long)[peripheral maximumWriteValueLengthForType:CBCharacteristicWriteWithoutResponse],
        peripheral.canSendWriteWithoutResponse ? @"yes" : @"no"
    );

    if (notifyCharacteristic != nil) {
        self.notifyCharacteristic = notifyCharacteristic;
        LogLine(@"Discovering descriptors on %@", notifyCharacteristic.UUID.UUIDString);
        [peripheral discoverDescriptorsForCharacteristic:notifyCharacteristic];
        return;
    }

    LogLine(@"Notify characteristic not found; continuing without notifications");
    [self beginSendingWhenReady];
}

- (void)peripheral:(CBPeripheral *)peripheral
didDiscoverDescriptorsForCharacteristic:(CBCharacteristic *)characteristic
             error:(NSError *)error {
    if (error != nil) {
        [self finish:[NSString stringWithFormat:@"Descriptor discovery failed: %@", error] code:1];
        return;
    }
    CBDescriptor *notifyDescriptor = nil;
    for (CBDescriptor *descriptor in characteristic.descriptors) {
        if ([descriptor.UUID isEqual:NotifyDescriptorUUID()]) {
            notifyDescriptor = descriptor;
            break;
        }
    }
    if (notifyDescriptor != nil) {
        LogLine(@"Reading notification descriptor %@", notifyDescriptor.UUID.UUIDString);
        [peripheral readValueForDescriptor:notifyDescriptor];
        return;
    }
    LogLine(@"Notify descriptor not found; enabling notifications directly");
    [peripheral setNotifyValue:YES forCharacteristic:characteristic];
}

- (void)peripheral:(CBPeripheral *)peripheral
didUpdateValueForDescriptor:(CBDescriptor *)descriptor
             error:(NSError *)error {
    if (error != nil) {
        [self finish:[NSString stringWithFormat:@"Descriptor read failed: %@", error] code:1];
        return;
    }
    LogLine(@"Notification descriptor value read; enabling notifications");
    [peripheral setNotifyValue:YES forCharacteristic:self.notifyCharacteristic];
}

- (void)peripheral:(CBPeripheral *)peripheral
didUpdateNotificationStateForCharacteristic:(CBCharacteristic *)characteristic
             error:(NSError *)error {
    if (![characteristic.UUID isEqual:NotifyUUID()]) return;
    if (error != nil) {
        [self finish:[NSString stringWithFormat:@"Notification setup failed: %@", error] code:1];
        return;
    }
    LogLine(@"Notifications enabled: %@", characteristic.isNotifying ? @"yes" : @"no");
    [self beginSendingWhenReady];
}

- (void)beginSendingWhenReady {
    if (!self.shouldSend) {
        NSUInteger index = 1;
        for (NSData *packet in self.packets) {
            NSMutableArray<NSString *> *parts = [NSMutableArray array];
            const uint8_t *bytes = packet.bytes;
            for (NSUInteger i = 0; i < packet.length; i++) {
                [parts addObject:[NSString stringWithFormat:@"%02x", bytes[i]]];
            }
            LogLine(@"%02lu: %@", (unsigned long)index, [parts componentsJoinedByString:@" "]);
            index++;
        }
        [self finish:@"Dry run complete. Add --send to write." code:0];
        return;
    }

    if (self.sendStarted) return;
    self.sendStarted = YES;
    LogLine(@"Waiting 5.0 seconds before first write");
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(5.0 * NSEC_PER_SEC)), self.managerQueue, ^{
        [self sendNextPacketWhenReady];
    });
}

- (void)sendNextPacketWhenReady {
    if (self.sendCompleted) return;
    if (self.packetIndex >= self.packets.count) {
        self.sendCompleted = YES;
        LogLine(@"Waiting 5.0 seconds after final write");
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(5.0 * NSEC_PER_SEC)), self.managerQueue, ^{
            [self finish:@"Done" code:0];
        });
        return;
    }

    if (!self.peripheral.canSendWriteWithoutResponse) {
        LogLine(@"Peripheral not ready for write without response; waiting");
        self.waitingForWriteReady = YES;
        return;
    }

    self.waitingForWriteReady = NO;
    NSData *packet = self.packets[self.packetIndex];
    [self.peripheral writeValue:packet forCharacteristic:self.writeCharacteristic type:CBCharacteristicWriteWithoutResponse];
    self.packetIndex += 1;
    LogLine(@"Sent packet %lu/%lu: %lu bytes", (unsigned long)self.packetIndex, (unsigned long)self.packets.count, (unsigned long)packet.length);
    NSTimeInterval delayAfterPacket = [packet isEqualToData:ResetPacket()] ? 0.5 : self.delay;
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(delayAfterPacket * NSEC_PER_SEC)), self.managerQueue, ^{
        [self sendNextPacketWhenReady];
    });
}

- (void)peripheralIsReadyToSendWriteWithoutResponse:(CBPeripheral *)peripheral {
    LogLine(@"Peripheral reported ready for write without response");
    if (self.waitingForWriteReady) {
        [self sendNextPacketWhenReady];
    }
}

@end

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSArray<NSString *> *args = [[NSProcessInfo processInfo] arguments];
        NSString *packetPath = ArgValue(args, @"--packets", nil);
        LogPath = ArgValue(args, @"--log", nil);
        LogLine(@"Started %@", [args componentsJoinedByString:@" "]);
        if (packetPath == nil) {
            LogLine(@"Usage: BLEWritePackets --packets packets.hex [--send] [--name \"MI Matrix Display\"]");
            return 2;
        }

        NSError *error = nil;
        NSArray<NSData *> *packets = LoadPackets(packetPath, &error);
        if (packets == nil || packets.count == 0) {
            LogLine(@"Could not load packets: %@", error);
            return 2;
        }
        LogLine(@"Loaded %lu packets from %@", (unsigned long)packets.count, packetPath);

        NSString *targetName = ArgValue(args, @"--name", @"MI Matrix Display");
        NSTimeInterval delay = [ArgValue(args, @"--delay", @"0.05") doubleValue];
        BOOL shouldSend = [args containsObject:@"--send"];

        __unused BLEPacketWriter *writer = [[BLEPacketWriter alloc] initWithPackets:packets
                                                                         targetName:targetName
                                                                         shouldSend:shouldSend
                                                                              delay:delay];
        dispatch_main();
    }
    return 0;
}
