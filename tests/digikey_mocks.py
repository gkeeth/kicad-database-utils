from unittest.mock import MagicMock


def _create_digikey_generic_mock(
    category,
    mfg,
    MPN,
    digikey_PN,
    subcategory=None,
    family=None,
    series=None,
    parameters={},
):
    mock_part = MagicMock()
    mock_part.limited_taxonomy.value = category
    if subcategory:
        mock_part.limited_taxonomy.children = [MagicMock(value=subcategory)]
    if family:
        mock_part.family.value = family
    if series:
        mock_part.series.value = series
    mock_part.primary_datasheet = "<datasheet>"
    mock_part.manufacturer.value = mfg
    mock_part.manufacturer_part_number = MPN
    mock_part.digi_key_part_number = digikey_PN
    mock_part.parameters = [
        MagicMock(parameter=k, value=parameters[k]) for k in parameters
    ]
    return mock_part


def create_digikey_resistor_mock(
    resistance, tolerance, power, composition, package, **kwargs
):
    parameters = {
        "Resistance": resistance,
        "Tolerance": tolerance,
        "Power (Watts)": power,
        "Composition": composition,
        "Supplier Device Package": package,
    }
    return _create_digikey_generic_mock(
        category="Resistors", parameters=parameters, **kwargs
    )


def create_digikey_capacitor_mock(
    capacitance,
    tolerance,
    voltage,
    package,
    family,
    tempco=None,
    polarization=None,
    package_size=None,
    height=None,
    lead_spacing=None,
    **kwargs,
):
    parameters = {
        "Capacitance": capacitance,
        "Tolerance": tolerance,
        "Voltage - Rated": voltage,
        "Package / Case": package,
    }
    if tempco:
        parameters["Temperature Coefficient"] = tempco
    if polarization:
        parameters["Polarization"] = polarization
    if package_size:
        parameters["Size / Dimension"] = package_size
    if height:
        parameters["Height - Seated (Max)"] = height
    if lead_spacing:
        parameters["Lead Spacing"] = lead_spacing

    return _create_digikey_generic_mock(
        category="Capacitors", family=family, parameters=parameters, **kwargs
    )


def create_digikey_opamp_mock(
    bandwidth, slewrate, package, short_package, num_units, **kwargs
):
    parameters = {
        "Gain Bandwidth Product": bandwidth,
        "Slew Rate": slewrate,
        "Package / Case": package,
        "Supplier Device Package": short_package,
        "Number of Circuits": num_units,
    }

    return _create_digikey_generic_mock(
        category="Integrated Circuits (ICs)",
        subcategory=(
            "Linear - Amplifiers - Instrumentation, OP Amps, Buffer Amps "
            "- Amplifiers - Instrumentation, OP Amps, Buffer Amps"
        ),
        parameters=parameters,
        **kwargs,
    )


def create_digikey_microcontroller_mock(core, speed, package, **kwargs):
    parameters = {
        "Core Processor": core,
        "Speed": speed,
        "Supplier Device Package": package,
    }

    return _create_digikey_generic_mock(
        category="Integrated Circuits (ICs)",
        subcategory="Embedded - Microcontrollers - Microcontrollers",
        parameters=parameters,
        **kwargs,
    )


def create_digikey_vreg_mock(
    vout_min, vout_max, vin_max, iout, output_type, package, **kwargs
):
    parameters = {
        "Supplier Device Package": package,
        "Voltage - Output (Min/Fixed)": vout_min,
        "Voltage - Output (Max)": vout_max,
        "Voltage - Input (Max)": vin_max,
        "Current - Output": iout,
        "Output Type": output_type,
    }

    return _create_digikey_generic_mock(
        category="Integrated Circuits (ICs)",
        subcategory=(
            "Power Management (PMIC) - Voltage Regulators - Linear, "
            "Low Drop Out (LDO) Regulators - Voltage Regulators - "
            "Linear, Low Drop Out (LDO) Regulators"
        ),
        parameters=parameters,
        **kwargs,
    )


def create_digikey_diode_mock(
    reverse_voltage,
    package,
    current_or_power,
    diode_type=None,
    diode_configuration="",
    **kwargs,
):
    parameters = {
        "Supplier Device Package": package,
    }
    if diode_configuration:
        parameters["Diode Configuration"] = diode_configuration
    if diode_type in ("Standard", "Schottky"):
        parameters["Voltage - DC Reverse (Vr) (Max)"] = reverse_voltage
        parameters["Current - Average Rectified (Io)"] = current_or_power
        parameters["Technology"] = diode_type
        subcategory = "Diodes - Rectifiers - Single Diodes - Rectifiers - Single Diodes"
    else:
        parameters["Voltage - Zener (Nom) (Vz)"] = reverse_voltage
        parameters["Power - Max"] = current_or_power
        subcategory = (
            "Diodes - Zener - Single Zener Diodes - Zener - Single Zener Diodes"
        )

    return _create_digikey_generic_mock(
        category="Discrete Semiconductor Products",
        subcategory=subcategory,
        parameters=parameters,
        **kwargs,
    )


def create_digikey_LED_mock(
    color,
    diode_configuration,
    forward_voltage="",
    interface="",
    supplier_device_package="",
    package="",
    size_dimension="",
    **kwargs,
):
    parameters = {
        "Color": color,
        "Configuration": diode_configuration,
    }
    if forward_voltage:
        parameters["Voltage - Forward (Vf) (Typ)"] = forward_voltage
    if interface:
        parameters["Interface"] = interface
    if package:
        parameters["Package / Case"] = package
    if supplier_device_package:
        parameters["Supplier Device Package"] = supplier_device_package
    if size_dimension:
        parameters["Size / Dimension"] = size_dimension

    return _create_digikey_generic_mock(
        category="Optoelectronics", parameters=parameters, **kwargs
    )


def create_digikey_BJT_mock(
    transistor_type, vce_max, ic_max, power_max, ft, package, **kwargs
):
    parameters = {
        "Transistor Type": transistor_type,
        "Voltage - Collector Emitter Breakdown (Max)": vce_max,
        "Current - Collector (Ic) (Max)": ic_max,
        "Power - Max": power_max,
        "Frequency - Transition": ft,
        "Supplier Device Package": package,
    }

    return _create_digikey_generic_mock(
        category="Discrete Semiconductor Products",
        subcategory=(
            "Transistors - Bipolar (BJT) - "
            "Single Bipolar Transistors - Bipolar (BJT) - "
            "Single Bipolar Transistors"
        ),
        parameters=parameters,
        **kwargs,
    )


def create_digikey_connector_mock(
    positions,
    rows,
    mounting_type,
    pitch,
    series,
    shrouding,
    connector_type,
    contact_type,
    fastening_type,
    features,
    **kwargs,
):
    parameters = {
        "Number of Positions": positions,
        "Number of Rows": rows,
        "Mounting Type": mounting_type,
        "Pitch - Mating": pitch,
        "Shrouding": shrouding,
        "Connector Type": connector_type,
        "Contact Type": contact_type,
        "Fastening Type": fastening_type,
        "Features": features,
    }

    return _create_digikey_generic_mock(
        category="Connectors, Interconnects",
        series=series,
        parameters=parameters,
        **kwargs,
    )


mock_resistor = create_digikey_resistor_mock(
    resistance="100Ω",
    tolerance="±1%",
    power="0.1W",
    composition="Thin Film",
    package="0603",
    mfg="YAGEO",
    MPN="RT0603FRE07100RL",
    digikey_PN="YAG2320CT-ND",
)


mock_jumper = create_digikey_resistor_mock(
    resistance="0 Ohms",
    tolerance="Jumper",
    power="-",
    composition="Thick Film",
    package="0603",
    mfg="YAGEO",
    MPN="RC0603JR-070RL",
    digikey_PN="311-0.0GRCT-ND",
)


mock_ceramic_capacitor = create_digikey_capacitor_mock(
    family="Ceramic Capacitors",
    mfg="Samsung Electro-Mechanics",
    MPN="CL21B334KBFNNNE",
    digikey_PN="1276-1123-1-ND",
    capacitance="0.33 µF",
    tolerance="±10%",
    voltage="50V",
    tempco="X7R",
    package="0805 (2012 Metric)",
)


mock_electrolytic_capacitor = create_digikey_capacitor_mock(
    family="Aluminum Electrolytic Capacitors",
    mfg="Nichicon",
    MPN="UCY2G100MPD1TD",
    digikey_PN="493-13313-1-ND",
    capacitance="10 µF",
    tolerance="±20%",
    voltage="400V",
    package="Radial, Can",
    polarization="Polar",
    package_size='0.394" Dia (10.00mm)',
    height='0.689" (17.50mm)',
    lead_spacing='0.197" (5.00mm)',
)


mock_unpolarized_electrolytic_capacitor = create_digikey_capacitor_mock(
    family="Aluminum Electrolytic Capacitors",
    mfg="Panasonic Electronic Components",
    MPN="ECE-A1HN100UB",
    digikey_PN="10-ECE-A1HN100UBCT-ND",
    capacitance="10 µF",
    tolerance="±20%",
    voltage="50V",
    package="Radial, Can",
    polarization="Bi-Polar",
    package_size='0.248" Dia (6.30mm)',
    height='0.480" (12.20mm)',
    lead_spacing='0.197" (5.00mm)',
)


mock_opamp = create_digikey_opamp_mock(
    mfg="Texas Instruments",
    MPN="LM4562MAX/NOPB",
    digikey_PN="296-35279-1-ND",
    bandwidth="55 MHz",
    slewrate="20V/µs",
    package='8-SOIC (0.154", 3.90mm Width)',
    short_package="8-SOIC",
    num_units="2",
)


mock_microcontroller = create_digikey_microcontroller_mock(
    mfg="STMicroelectronics",
    MPN="STM32F042K4T6TR",
    digikey_PN="STM32F042K4T6TR-ND",
    core="ARM® Cortex®-M0",
    package="32-LQFP (7x7)",
    speed="48MHz",
)


mock_vreg_pos_adj = create_digikey_vreg_mock(
    mfg="Texas Instruments",
    MPN="LM317HVT/NOPB",
    digikey_PN="LM317HVT/NOPB-ND",
    package="TO-220-3",
    vout_min="1.25V",
    vout_max="57V",
    vin_max="60V",
    iout="1.5A",
    output_type="Adjustable",
)


mock_vreg_neg_fixed = create_digikey_vreg_mock(
    mfg="Texas Instruments",
    MPN="LM7912CT/NOPB",
    digikey_PN="LM7912CT/NOPB-ND",
    package="TO-220-3",
    vout_min="-12V",
    vout_max="-",
    vin_max="-35V",
    iout="1.5A",
    output_type="Fixed",
)


mock_diode = create_digikey_diode_mock(
    mfg="onsemi",
    MPN="1N4148TR",
    digikey_PN="1N4148FSCT-ND",
    package="DO-35",
    reverse_voltage="100 V",
    current_or_power="200mA",
    diode_type="Standard",
)


mock_schottky_diode = create_digikey_diode_mock(
    mfg="Diodes Incorporated",
    MPN="BAT54WS-7-F",
    digikey_PN="BAT54WS-FDICT-ND",
    package="SOD-323",
    reverse_voltage="30 V",
    current_or_power="100mA",
    diode_type="Schottky",
)


mock_zener_diode = create_digikey_diode_mock(
    mfg="Diodes Incorporated",
    MPN="MMSZ5231B-7-F",
    digikey_PN="MMSZ5231B-FDICT-ND",
    package="SOD-123",
    reverse_voltage="5.1 V",
    current_or_power="500mW",
)


mock_diode_array = create_digikey_diode_mock(
    mfg="Micro Commercial Co",
    MPN="BAV99-TP",
    digikey_PN="BAV99TPMSCT-ND",
    package="SOT-23",
    reverse_voltage="70 V",
    current_or_power="200mA",
    diode_type="Standard",
    diode_configuration="1 Pair Series Connection",
)


mock_led = create_digikey_LED_mock(
    mfg="Lite-On Inc.",
    MPN="LTST-C191KFKT",
    digikey_PN="160-1445-1-ND",
    color="Orange",
    forward_voltage="2V",
    diode_configuration="Standard",
    package="0603 (1608 Metric)",
)


mock_rgb_led = create_digikey_LED_mock(
    mfg="Kingbright",
    MPN="WP154A4SUREQBFZGC",
    digikey_PN="754-1615-ND",
    color="Red, Green, Blue (RGB)",
    forward_voltage="1.9V Red, 3.3V Green, 3.3V Blue",
    diode_configuration="Common Cathode",
    package="Radial - 4 Leads",
    supplier_device_package="T-1 3/4",
)


mock_addressable_led = create_digikey_LED_mock(
    mfg="Inolux",
    MPN="IN-PI554FCH",
    digikey_PN="1830-1106-1-ND",
    color="Red, Green, Blue (RGB)",
    diode_configuration="Discrete",
    interface="PWM",
    size_dimension="5.00mm L x 5.00mm W",
)


mock_bjt = create_digikey_BJT_mock(
    mfg="onsemi",
    MPN="2N3904BU",
    digikey_PN="2N3904FS-ND",
    transistor_type="NPN",
    vce_max="40 V",
    ic_max="200 mA",
    power_max="625 mW",
    ft="300MHz",
    package="TO-92-3",
)


mock_bjt_array = create_digikey_BJT_mock(
    mfg="onsemi",
    MPN="MMPQ3904",
    digikey_PN="MMPQ3904FSCT-ND",
    transistor_type="4 NPN (Quad)",
    vce_max="40V",
    ic_max="200mA",
    power_max="1W",
    ft="250MHz",
    package="16-SOIC",
)


mock_shrouded_connector = create_digikey_connector_mock(
    mfg="Molex",
    MPN="1719710004",
    digikey_PN="WM22646-ND",
    positions="4",
    rows="1",
    pitch='0.100" (2.54mm)',
    series="SL 171971",
    shrouding="Shrouded",
    connector_type="Header",
    mounting_type="Through Hole",
    contact_type="Male Pin",
    fastening_type="Latch Holder",
    features="Polarizing Key",
)

mock_unshrouded_connector = create_digikey_connector_mock(
    mfg="Amphenol ICC (FCI)",
    MPN="67996-406HLF",
    digikey_PN="609-3218-ND",
    positions="6",
    rows="2",
    pitch='0.100" (2.54mm)',
    series="BERGSTIK® II",
    shrouding="Unshrouded",
    connector_type="Header",
    mounting_type="Through Hole",
    contact_type="Male Pin",
    fastening_type="Push-Pull",
    features="-",
)
