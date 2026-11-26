# Firmware

All three sketches compile for ESP32-C3 (checked 2026-11-26). None has been flashed or bench-tested yet.

**Pinned toolchain**
- **Core:** Arduino-ESP32 core **3.3.13**. Core 4.0.0 currently fails: NimBLE-Arduino 2.5.2 doesn't build against it.
- **Library:** NimBLE-Arduino **2.5.2**.

```sh
brew install arduino-cli
arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core update-index
arduino-cli core install esp32:esp32@3.3.13
arduino-cli lib install NimBLE-Arduino@2.5.2

arduino-cli compile --fqbn esp32:esp32:esp32c3 firmware/beacon
arduino-cli compile --fqbn esp32:esp32:esp32c3 firmware/gateway
arduino-cli compile --fqbn esp32:esp32:esp32c3 firmware/badge
# flash: add  -u -p /dev/cu.usbmodemXXXX
```

| Sketch | Flash used | Per-unit setting |
|---|---|---|
| beacon | 41% | `ZONE_ID` |
| gateway | 73% | none |
| badge | 91% | `BADGE_ID`. If it grows past the default partition, use `--board-options PartitionScheme=huge_app` |

The protocol structs are copied into each sketch, so change all three together. The badge and gateway are on ESP-NOW channel 1.
