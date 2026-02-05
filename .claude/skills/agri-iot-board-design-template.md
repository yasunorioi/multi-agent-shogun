# Agricultural IoT Board Design Template - Skill Definition

**Skill ID**: `agri-iot-board-design-template`
**Category**: Hardware Design / PCB Design
**Version**: 1.0.0
**Created**: 2026-02-05
**Platform**: JLCPCB / KiCad

---

## Overview

This skill provides a comprehensive template for designing custom PCBs for agricultural IoT nodes. It covers Grove Shield alternative designs, relay control circuits, I2C bus extension with P82B96, and JLCPCB-ready component selection with LCSC part numbers.

---

## Use Cases

- **Greenhouse Sensor Node**: Temperature, humidity, CO2 monitoring with solenoid valve control
- **Irrigation Controller**: Soil moisture sensing with single valve control
- **Environmental Monitoring**: Multi-sensor nodes with long cable runs (5-20m)
- **Retrofit Projects**: Adding IoT capability to existing greenhouse equipment

---

## Target Configuration

```
W5500-EVB-Pico-PoE (Base Board)
       │
       └── Custom Expansion Board
           ├── Grove Connectors (I2C x2, ADC x1)
           ├── Relay 1ch (Solenoid Valve Control)
           ├── P82B96 I2C Buffer (5-20m Cable Extension)
           ├── Screw Terminals (Field Wiring)
           └── Status LEDs
```

---

## Design Sections

### 1. Grove Shield Alternative Design

#### Purpose

Replace discontinued Grove Shield for Pi Pico with custom PCB for production.

#### Grove Connector Pinout (HY2.0-4P)

| Pin | I2C Function | ADC Function |
|-----|--------------|--------------|
| 1   | GND          | GND          |
| 2   | VCC (3.3V)   | VCC (3.3V)   |
| 3   | SDA          | NC           |
| 4   | SCL          | Signal       |

#### Recommended Layout

```
┌─────────────────────────────────────────┐
│  [Grove I2C-1]  [Grove I2C-2]  [Grove ADC] │
│      │              │              │      │
│      └──────────────┴──────────────┘      │
│                     │                      │
│              ┌──────┴──────┐               │
│              │   P82B96    │               │
│              │ I2C Buffer  │               │
│              └──────┬──────┘               │
│                     │                      │
│  [EXT I2C] ←────────┘      [Relay 1ch]    │
│                                  │         │
│  [Terminal Block] ←──────────────┘         │
│                                            │
│  ════════════════════════════════════      │
│  │ Pin Header for W5500-EVB-Pico-PoE │     │
│  ════════════════════════════════════      │
└─────────────────────────────────────────┘
```

---

### 2. P82B96 I2C Bus Buffer Circuit

#### Overview

The P82B96 is a dual bidirectional I2C bus buffer that enables cable extension up to 20+ meters while maintaining 400kHz Fast I2C operation.

#### Key Specifications

| Parameter | Main Side (Sx/Sy) | Transmission Side (Tx/Ty) |
|-----------|-------------------|---------------------------|
| Max Capacitance | 400 pF | 4000 pF |
| Voltage Range | 2V - 15V | 2V - 15V |
| Max Cable Length | - | 20+ meters |
| I2C Speed | 400 kHz (Fast mode) | 400 kHz |

#### Circuit Diagram

```
                      P82B96
                   ┌─────────┐
    Pico SDA ──────┤ Sx   Tx ├──────┬───── EXT_SDA (to remote sensor)
                   │         │      │
    Pico SCL ──────┤ Sy   Ty ├──────┼───── EXT_SCL (to remote sensor)
                   │         │      │
         VCC ──────┤ VCC     │      │
                   │         │      │
         GND ──────┤ GND     │      │
                   └─────────┘      │
                                    │
              Local Side          Remote Side
              (< 0.5m)           (5-20m cable)

    Pull-up Resistors:
    ────────────────────────────────────────────
    Pico SDA ──[4.7kΩ]── VCC    EXT_SDA ──[2.2kΩ]── VCC
    Pico SCL ──[4.7kΩ]── VCC    EXT_SCL ──[2.2kΩ]── VCC
```

#### Design Notes

1. **Pull-up Resistors**
   - Local side (Sx/Sy): 4.7kΩ (standard I2C)
   - Remote side (Tx/Ty): 2.2kΩ (stronger pull-up for long cables)

2. **Cable Requirements**
   - Use twisted pair cable (Cat5e or shielded)
   - SDA and SCL on separate twisted pairs
   - Connect shield to GND at one end only

3. **推奨ケーブル: M5Stack GROVE互換ケーブル**
   - スイッチサイエンスで購入可能
   - 100cm (¥550): https://www.switch-science.com/products/5216
   - 200cm: https://www.switch-science.com/products/5217
   - Grove端子付きでそのまま接続可能
   - P82B96と併用で5〜20m延長OK

3. **Decoupling Capacitors**
   - Add 100nF ceramic capacitor near P82B96 VCC pin
   - Add 100nF at remote sensor VCC

#### P82B96 Pin Configuration (SOIC-8)

| Pin | Name | Function |
|-----|------|----------|
| 1   | Sx   | SDA (local side) |
| 2   | Sy   | SCL (local side) |
| 3   | Ty   | SCL (transmission/remote side) |
| 4   | GND  | Ground |
| 5   | Tx   | SDA (transmission/remote side) |
| 6   | NC   | No connection |
| 7   | NC   | No connection |
| 8   | VCC  | Power supply (3.3V or 5V) |

---

### 3. Relay Driver Circuit (1 Channel)

#### Circuit Diagram

```
    GPIO Pin (3.3V) ──[1kΩ]──┬── Base
                             │
                           ┌─┴─┐
                           │   │ 2N2222A (NPN)
                           └─┬─┘
                             │ Collector
                             │
                         ┌───┴───┐
                         │       │
                         │ RELAY │ SRD-05VDC-SL-C
                         │  (5V) │
                         │       │
                         └───┬───┘
                             │ Coil+
                             │
         5V ────────────┬────┘
                        │
                   ┌────┴────┐
                   │ 1N4148  │ Flyback Diode
                   │  ◀──    │ (cathode to 5V)
                   └────┬────┘
                        │
                        └──── Coil-
                             │
         GND ────────────────┴──── Emitter


    LED Indicator:
    ─────────────────────────────────────
    Relay NO ──[330Ω]──[LED]── GND
```

#### Component Selection

| Component | Value | Purpose |
|-----------|-------|---------|
| Base Resistor | 1kΩ | Limit base current (~3mA) |
| Flyback Diode | 1N4148 | Suppress back-EMF |
| LED Resistor | 330Ω | Limit LED current (~10mA) |
| Relay | 5V SPDT | Solenoid valve control |

#### Relay Specifications (SRD-05VDC-SL-C)

| Parameter | Value |
|-----------|-------|
| Coil Voltage | 5V DC |
| Coil Current | ~70mA |
| Contact Rating | 10A @ 250VAC |
| Contact Type | SPDT (NO/NC/COM) |

#### Screw Terminal Wiring

```
    ┌─────────────────┐
    │ 1: COM          │ → Common (valve power)
    │ 2: NO           │ → Normally Open (valve+)
    │ 3: NC           │ → Normally Closed (unused)
    └─────────────────┘
```

---

### 4. JLCPCB Component Selection (LCSC Part Numbers)

#### Bill of Materials (BOM)

| Component | Description | LCSC Part # | Qty | Unit Price | Extended |
|-----------|-------------|-------------|-----|------------|----------|
| **Connectors** |
| Grove Connector | HY2.0-4P SMD | C722729 | 3 | $0.04 | $0.12 |
| Pin Header | 2.54mm 2x20P | C50980 | 1 | $0.08 | $0.08 |
| Screw Terminal | 5mm 2P | C395868 | 2 | $0.09 | $0.18 |
| **I2C Buffer** |
| P82B96TD,118 | I2C Buffer SOIC-8 | C32103 | 1 | $1.50 | $1.50 |
| **Relay Circuit** |
| SRD-05VDC-SL-C | 5V Relay SPDT | C35449 | 1 | $0.26 | $0.26 |
| 2N2222A | NPN Transistor SOT-23 | C118536 | 1 | $0.02 | $0.02 |
| 1N4148 | Flyback Diode SOD-323 | C14516 | 1 | $0.004 | $0.004 |
| **Passives** |
| Resistor 1kΩ | 0603 1% | C22548 | 1 | $0.001 | $0.001 |
| Resistor 330Ω | 0603 1% | C23138 | 1 | $0.001 | $0.001 |
| Resistor 4.7kΩ | 0603 1% | C23162 | 2 | $0.001 | $0.002 |
| Resistor 2.2kΩ | 0603 1% | C22975 | 2 | $0.001 | $0.002 |
| Capacitor 100nF | 0603 X7R | C14663 | 3 | $0.001 | $0.003 |
| **Indicators** |
| LED Green | 0603 SMD | C125098 | 2 | $0.01 | $0.02 |
| | | | **Subtotal** | | **$2.19** |

#### PCB Manufacturing Cost (JLCPCB)

| Quantity | PCB Cost | Assembly | Total/Board |
|----------|----------|----------|-------------|
| 5 pcs | $2.00 | $8.00 + parts | ~$4.20 |
| 10 pcs | $2.00 | $8.00 + parts | ~$3.22 |
| 50 pcs | $5.00 | $8.00 + parts | ~$2.45 |

**Note**: Assembly cost is $8.00 setup + $0.0017/joint. Extended parts (P82B96) may add $3 handling fee.

#### Total Cost Estimate (Per Board)

| Quantity | Components | PCB + Assembly | Total |
|----------|------------|----------------|-------|
| 5 pcs | $2.19 | $2.80 | **$4.99** |
| 10 pcs | $2.19 | $1.30 | **$3.49** |
| 50 pcs | $2.19 | $0.36 | **$2.55** |

---

### 5. KiCad Design Reference

#### Schematic Blocks

```
Sheet 1: Power & Connectors
─────────────────────────────────
┌─────────────┐
│ Pin Header  │──── 3.3V ────┬─── Grove VCC
│ (Pico)      │              │
│             │──── 5V  ─────┼─── Relay VCC
│             │              │
│             │──── GND ─────┴─── Common GND
│             │
│             │──── SDA ─────────┐
│             │                  │
│             │──── SCL ─────────┼─── To I2C Buffer
│             │                  │
│             │──── GPIO ────────┼─── To Relay Driver
└─────────────┘                  │
                                 │
Sheet 2: I2C Buffer              │
─────────────────────────────────
┌─────────────┐                  │
│   P82B96    │◀─────────────────┘
│             │
│ Sx ──── Tx  │──── EXT_SDA
│ Sy ──── Ty  │──── EXT_SCL
│             │
└─────────────┘

Sheet 3: Relay Driver
─────────────────────────────────
GPIO ──[R1]── 2N2222A ──┬── Relay ──┬── Terminal
                        │           │
                     1N4148        LED
```

#### Recommended PCB Size

| Parameter | Value |
|-----------|-------|
| Width | 50mm |
| Height | 40mm |
| Layers | 2 |
| Thickness | 1.6mm |
| Copper | 1oz |

#### Design Rules (JLCPCB Standard)

| Parameter | Minimum |
|-----------|---------|
| Trace Width | 0.127mm (5mil) |
| Trace Spacing | 0.127mm (5mil) |
| Via Diameter | 0.3mm |
| Via Drill | 0.2mm |
| Silkscreen | 0.15mm line, 0.8mm text |

---

## Circuit Block Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                   Custom Expansion Board                        │
│                                                                │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                    │
│  │Grove I2C│    │Grove I2C│    │Grove ADC│                    │
│  │   #1    │    │   #2    │    │   #1    │                    │
│  └────┬────┘    └────┬────┘    └────┬────┘                    │
│       │              │              │                          │
│       └──────┬───────┘              │                          │
│              │ I2C Bus              │ ADC                      │
│              ▼                      ▼                          │
│       ┌──────────┐           ┌──────────┐                     │
│       │  P82B96  │           │  Direct  │                     │
│       │  Buffer  │           │  to Pico │                     │
│       └────┬─────┘           └──────────┘                     │
│            │                                                   │
│            ▼ Extended I2C                                      │
│       ┌──────────┐                                            │
│       │ Terminal │ → To remote sensor (5-20m)                 │
│       │  Block   │                                            │
│       └──────────┘                                            │
│                                                                │
│       ┌──────────┐    ┌──────────┐    ┌──────────┐           │
│       │   GPIO   │───▶│  Relay   │───▶│ Terminal │           │
│       │ (Pico)   │    │  Driver  │    │  Block   │           │
│       └──────────┘    └──────────┘    └──────────┘           │
│                              │                                 │
│                              ▼                                 │
│                        ┌──────────┐                           │
│                        │ Status   │                           │
│                        │   LED    │                           │
│                        └──────────┘                           │
│                                                                │
│  ══════════════════════════════════════════════════════       │
│  ║  2x20 Pin Header (connects to W5500-EVB-Pico-PoE)  ║       │
│  ══════════════════════════════════════════════════════       │
└────────────────────────────────────────────────────────────────┘
```

---

## Power Distribution

```
     PoE (via W5500-EVB-Pico-PoE)
              │
              ▼
    ┌─────────────────┐
    │   W5500-EVB     │
    │   Power Rails   │
    └────────┬────────┘
             │
     ┌───────┼───────┐
     │       │       │
     ▼       ▼       ▼
   3.3V     5V     GND
     │       │       │
     │       ├───────┼─── Relay Coil (5V)
     │       │       │
     ├───────┼───────┼─── P82B96 VCC (3.3V or 5V)
     │       │       │
     └───────┼───────┼─── Grove Connectors (3.3V)
             │       │
             └───────┴─── Remote Sensor (via cable)
```

---

## Implementation Checklist

### Design Phase
- [ ] Create KiCad schematic with all blocks
- [ ] Assign LCSC footprints to all components
- [ ] Generate netlist and run ERC
- [ ] Layout PCB (place connectors first, then ICs)
- [ ] Run DRC with JLCPCB rules
- [ ] Generate Gerber files

### Ordering Phase
- [ ] Upload Gerber to JLCPCB
- [ ] Select 2-layer, 1.6mm, green solder mask
- [ ] Enable SMT assembly
- [ ] Upload BOM (LCSC format)
- [ ] Upload CPL (component placement)
- [ ] Review assembly preview
- [ ] Place order

### Testing Phase
- [ ] Visual inspection of assembled board
- [ ] Continuity test (power rails)
- [ ] I2C scan (local Grove connectors)
- [ ] I2C scan (extended bus via P82B96)
- [ ] Relay test (GPIO toggle)
- [ ] Full integration test with sensors

---

## Common Issues and Solutions

### 1. I2C Communication Fails Over Long Cable

**Symptoms**: I2C scan returns no devices on extended bus

**Solutions**:
- Verify P82B96 orientation (pin 1 marker)
- Check pull-up resistors on both sides
- Reduce I2C speed to 100kHz
- Use shielded twisted pair cable
- Check cable length (max 20m recommended)

### 2. Relay Does Not Activate

**Symptoms**: GPIO high but relay stays off

**Solutions**:
- Verify 5V supply to relay
- Check transistor orientation (EBC pinout varies)
- Measure base resistor value
- Test relay coil directly with 5V

### 3. Sensor Readings Unstable

**Symptoms**: ADC or I2C values fluctuate

**Solutions**:
- Add decoupling capacitors near sensors
- Separate analog and digital grounds
- Use star grounding topology
- Shield cables from noise sources

---

## References

- [P82B96 Datasheet (TI)](https://www.ti.com/product/P82B96)
- [P82B96 Datasheet (NXP)](https://www.nxp.com/docs/en/data-sheet/P82B96.pdf)
- [JLCPCB Capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
- [LCSC Electronics](https://www.lcsc.com/)
- [KiCad JLCPCB Plugin](https://github.com/Bouni/kicad-jlcpcb-tools)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-05 | Initial release |

---

**Skill Author**: Arsprout Analysis Team
**License**: MIT
