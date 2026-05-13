# Protocol Notes

## Device identity

- Bluetooth serial port: `/dev/cu.MIMatrixDisplay`
- Bluetooth TTY name: `MIMatrixDisplay`
- Observed macOS device type: `Serial`
- Public BLE service UUID: `0000ffd0-0000-1000-8000-00805f9b34fb`
- Public write characteristic UUID: `0000ffd1-0000-1000-8000-00805f9b34fb`
- Public notify characteristic UUID: `0000ffd2-0000-1000-8000-00805f9b34fb`

## Packet format

- Packets start with `0xbc`.
- The body follows immediately.
- Checksum is the low byte of the sum of body bytes.
- Most packets end with `0x55`.
- A temporary image is sent as:
  - temp image write enable: `bc 0f f1 08 08 55`
  - eight image chunks
  - temp image write disable: `bc 0f f2 08 09 55`
- Each image chunk is two rows: 32 RGB pixels, 96 RGB bytes.

## First safe tests

- Passive read after opening the port.
- Dry-run the generated command sequence.
- Send a temporary generated image before trying saved images.

## Sources

- `offe/mi-led-display` includes Python BLE scripts and snoop logs.
- `LostBeard/SpawnDev.MatrixLEDDisplay` includes a working Web Bluetooth app.
