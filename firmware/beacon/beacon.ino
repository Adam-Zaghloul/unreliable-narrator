// Zone beacon (ESP32-C3). One per room or landmark. Advertise-only.
// NOT YET COMPILED OR BENCH-TESTED. Toolchain: Arduino-ESP32 core 3.x + NimBLE-Arduino 2.x.
//
// Manufacturer data: FF FF 'U' 'N' 'B' ZONE_ID. The hub maps ZONE_ID -> room name.
// Tip: mount every beacon at the same height and away from metal, and keep TX power equal,
// otherwise one room "wins" the RSSI comparison by default.

#include <NimBLEDevice.h>

#define ZONE_ID 1  // CHANGE PER BEACON (1..254)

// Core 4.x builds NimBLE with extended advertising on, which swaps the advertising API.
// This helper sends a plain legacy, non-connectable advert either way.
void startAdvertising(const std::string& md, uint16_t minUnits, uint16_t maxUnits) {
#if CONFIG_BT_NIMBLE_EXT_ADV
  NimBLEExtAdvertisement ad;
  ad.setLegacyAdvertising(true);
  ad.setConnectable(false);
  ad.setScannable(false);
  ad.setFlags(BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP);
  ad.setManufacturerData(md);
  ad.setMinInterval(minUnits);
  ad.setMaxInterval(maxUnits);
  NimBLEExtAdvertising* adv = NimBLEDevice::getAdvertising();
  adv->setInstanceData(0, ad);
  adv->start(0);
#else
  NimBLEAdvertisementData ad;
  ad.setFlags(BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP);
  ad.setManufacturerData(md);
  NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
  adv->setAdvertisementData(ad);
  adv->setMinInterval(minUnits);
  adv->setMaxInterval(maxUnits);
  adv->start();
#endif
}

void setup() {
  NimBLEDevice::init("");
  // 160 * 0.625 ms = 100 ms; max 110 ms, a little jitter avoids repeated collisions
  startAdvertising(std::string{(char)0xFF, (char)0xFF, 'U', 'N', 'B', (char)ZONE_ID}, 160, 176);
}

void loop() { delay(1000); }
