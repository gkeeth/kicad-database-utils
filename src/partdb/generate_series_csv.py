#! /usr/bin/env python

from component import Capacitor, Resistor, Connector

# fmt: off
E12 = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2]

E24 = [
    1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9,
    4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1
]

E96 = [
    1, 1.02, 1.05, 1.07, 1.1, 1.13, 1.15, 1.18, 1.21, 1.24, 1.27, 1.3, 1.33,
    1.37, 1.4, 1.43, 1.47, 1.5, 1.54, 1.58, 1.62, 1.65, 1.69, 1.74, 1.78, 1.82,
    1.87, 1.91, 1.96, 2, 2.05, 2.1, 2.15, 2.21, 2.26, 2.32, 2.37, 2.43, 2.49,
    2.55, 2.61, 2.67, 2.74, 2.8, 2.87, 2.94, 3.01, 3.09, 3.16, 3.24, 3.32, 3.4,
    3.48, 3.57, 3.65, 3.74, 3.83, 3.92, 4.02, 4.12, 4.22, 4.32, 4.42, 4.53,
    4.64, 4.75, 4.87, 4.99, 5.11, 5.23, 5.36, 5.49, 5.62, 5.76, 5.9, 6.04,
    6.19, 6.34, 6.49, 6.65, 6.81, 6.98, 7.15, 7.32, 7.5, 7.68, 7.87, 8.06,
    8.25, 8.45, 8.66, 8.87, 9.09, 9.31, 9.53, 9.76,
]

resistor_multipliers = [1, 10, 100, 1e3, 1e4, 1e5, 1e6, 1e7, 1e8]
capacitor_multipliers = [1e-11, 1e-10, 1e-9, 1e-8, 1e-7, 1e-6]
prefixes = {
    1e9: "M",
    1e6: "M",
    1e3: "k",
    1e0: "",
    1e-3: "m",
    1e-6: "μ",
    1e-9: "n",
    1e-12: "p",
    1e-15: "f",
}

packages = ["0603", "0805", "1206"]

power_ratings = {
    "0603": "0.1W",
    "0805": "0.125W",
    "1206": "0.25W",
}
# fmt: on


def value_to_string(value):
    for m in prefixes:
        if value >= m:
            return f"{value / m:.3g}{prefixes[m]}"


def construct_resistor(resistance, package):
    data = {
        "datasheet": "",
        "manufacturer": "",
        "MPN": "",
        "distributor1": "",
        "DPN1": "",
        "distributor2": "",
        "DPN2": "",
        "resistance": resistance,
        "tolerance": "1%",
        "power": power_ratings[package],
        "composition": "Thin Film",
        "package": package,
        "value": "${resistance}",
        "IPN": "R",
        "kicad_symbol": "Device:R",
    }

    Resistor.make_description(data)
    Resistor.make_keywords(data)
    Resistor._determine_footprint(data, data["package"])

    return Resistor(**data)


def construct_capacitor(capacitance, dielectric, tolerance, voltage, package):
    data = {
        "datasheet": "",
        "manufacturer": "",
        "MPN": "",
        "distributor1": "",
        "DPN1": "",
        "distributor2": "",
        "DPN2": "",
        "capacitance": capacitance,
        "dielectric": dielectric,
        "tolerance": tolerance,
        "voltage": voltage,
        "package": package,
        "value": "${Capacitance}",
        "IPN": "C",
        "kicad_symbol": "Device:C",
    }

    Capacitor._determine_metadata(data, "unpolarized", package, "")
    Capacitor._determine_footprint(data, "unpolarized", "")

    return Capacitor(**data)


def construct_pinheader(rows, cols):
    data = {
        "datasheet": "",
        "manufacturer": "",
        "MPN": "",
        "distributor1": "",
        "DPN1": "",
        "distributor2": "",
        "DPN2": "",
        "package": "Header",
        "value": f"{rows}x{cols} Header",
        "IPN": "CONN",
        "kicad_footprint": f"Connector_PinHeader_2.54mm:PinHeader_{rows}x{cols:02}_P2.54mm_Vertical",
    }
    if rows == 1:
        data["kicad_symbol"] = f"Connector:Conn_{rows:02}x{cols:02}_Pin"
    else:
        data["kicad_symbol"] = f"Connector_Generic:Conn_{rows:02}x{cols:02}_Odd_Even"

    data["description"] = f"{rows}x{cols} unshrouded pinheader, vertical, 2.54mm"
    data["keywords"] = ""

    return Connector(**data)


def print_capacitors():
    # dummy component for header
    print(construct_capacitor("0", "", "", "", "0603").to_csv(body=False), end="")
    for package in packages:
        for m in capacitor_multipliers:
            # start with COG / NP0 capacitors, which are E24 / 5%,
            # up to and including 10nF
            for val in E24:
                raw_capacitance = val * m
                if raw_capacitance > 10e-9:
                    break
                capacitance = value_to_string(raw_capacitance)
                print(
                    construct_capacitor(
                        capacitance, "C0G, NP0", "5%", "50V", package
                    ).to_csv(header=False),
                    end="",
                )
            # for values above 10nF, use 10% X7R capacitors with 10% tolerance
            for val in E12:
                raw_capacitance = val * m
                if raw_capacitance <= 10e-9:
                    continue
                capacitance = value_to_string(raw_capacitance)
                print(
                    construct_capacitor(
                        capacitance, "X7R", "10%", "50V", package
                    ).to_csv(header=False),
                    end="",
                )


def print_resistors():
    # dummy component for header
    print(construct_resistor("0", "0603").to_csv(body=False), end="")
    for package in packages:
        print(construct_resistor("0", package).to_csv(header=False), end="")
        for m in resistor_multipliers:
            for val in E96:
                resistance = value_to_string(val * m)
                print(
                    construct_resistor(resistance, package).to_csv(header=False), end=""
                )


def print_pinheaders():
    # dummy component for header
    print(construct_pinheader(rows=0, cols=0).to_csv(body=False), end="")
    for cols in range(1, 17):
        print(construct_pinheader(1, cols).to_csv(header=False), end="")


if __name__ == "__main__":
    output_capacitors = True
    output_resistors = False
    output_pinheaders = False

    if output_capacitors:
        print_capacitors()
    if output_resistors:
        print_resistors()
    if output_pinheaders:
        print_pinheaders()
