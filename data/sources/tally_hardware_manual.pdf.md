# Tally Hardware Manual

Document TM-HW-07, revision E, August 2026. Applies to Tally Tag TT-200, Tally Tag TT-200C and Tally Hub TH-4.

## 1. System overview

A Tally installation has three parts. **Tally Tags** are battery-powered load sensors mounted under shelf sections; they measure the weight of the stock on the shelf. Tags send readings over a sub-GHz radio link to a **Tally Hub**, a gateway that forwards the data to **Tally Cloud**, where stock levels, alerts and reports are available in the dashboard and through the REST API.

## 2. Tally Tag TT-200

- Measuring range: 0 to 150 kg per tag, with a resolution of 20 g.
- Power: 2 × CR123A lithium batteries.
- Battery life: about 28 months at the default reporting interval of 5 minutes, and about 11 months at a 1-minute reporting interval.
- Operating temperature: −20 °C to +50 °C.
- Radio: 868 MHz in the EU and 915 MHz in the US, with an indoor range of up to 60 m in line of sight.
- Ingress protection: IP54.

The **TT-200C** is the cold-storage variant for freezers and chilled rooms. It operates from −35 °C to +10 °C, is rated IP66, and uses the same batteries. At temperatures below −20 °C, expect battery life to drop by roughly 30%.

## 3. Tally Hub TH-4

- Capacity: up to 250 tags per hub. For reliable performance we recommend no more than 200.
- Uplink: Ethernet with PoE+ as the primary connection, with automatic LTE Cat-M1 fallback when Ethernet is unavailable.
- Offline buffer: if the hub loses its connection to Tally Cloud, it stores up to 72 hours of tag readings and uploads them automatically when the connection returns.
- Mounting height: at least 2 m above the floor, as central as possible within the area it serves.

## 4. Installation

1. Mount the hub centrally, no more than 60 m from the furthest tag, at least 2 m high.
2. Connect Ethernet (PoE+) or insert the LTE SIM. The hub LED turns solid white when it has booted and is online.
3. Claim the hub: in Tally Cloud, open Sites → Hubs → Add hub and enter the 12-character claim code printed on the hub label.
4. Pair each tag: press and hold the tag button for 5 seconds until its LED blinks blue. The tag joins the nearest hub that is in pairing mode. A hub stays in pairing mode for 10 minutes after you click "Pair tags" in the dashboard.
5. Calibrate each tag: with the shelf empty, run "Tare" in the dashboard, then place the 5 kg reference weight included in the installation kit and run "Calibrate".

A tag must be recalibrated whenever it is moved to a different shelf. Replacing batteries does not require recalibration.

## 5. LED status codes — Tally Tag

| LED pattern | Meaning | What to do |
|---|---|---|
| Blinking blue | Pairing mode | Wait until pairing completes |
| Solid green for 3 seconds | Paired successfully | Nothing |
| Amber blink every 30 seconds | Battery below 15% | Replace both batteries within 2 weeks |
| Blinking red | Cannot reach the hub | Check the distance to the hub and for obstacles; check the hub is online |
| Alternating red and amber | Load cell fault | Contact support to start an RMA |

## 6. LED status codes — Tally Hub

| LED pattern | Meaning | What to do |
|---|---|---|
| Solid white | Booted and online | Nothing |
| Pulsing cyan | Firmware update in progress | Do not unplug the hub |
| Solid amber | Online through the LTE fallback | Check the Ethernet connection |
| Blinking red | No uplink at all | Check cabling, PoE+ power and the SIM |

## 7. Firmware

Hubs install firmware updates automatically during the maintenance window of 02:00 to 04:00 in the site's local time. The hub then updates its tags over the air, one tag at a time, so tag updates for a large site can take several nights. Current versions are hub firmware 5.8.2 and tag firmware 2.4.0.

## 8. Factory reset

To factory-reset a hub, press and hold the recessed reset pin for 15 seconds until the LED flashes magenta three times. A reset hub must be claimed again in Tally Cloud, but its paired tags reconnect automatically within about 10 minutes. To reset a tag, remove one battery, hold the button, and reinsert the battery while holding the button for 10 seconds.

## 9. Safety and disposal

Use only CR123A lithium batteries. Do not mix old and new batteries. Dispose of used batteries and devices according to local e-waste regulations; in the EU, devices can be returned to Brindlewave free of charge for recycling.
