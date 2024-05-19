import csv
import io
import re
import readline  # noqa: F401
from abc import ABC, abstractmethod
from collections import OrderedDict

from partdb import db
from partdb.print_utils import print_error

"""
TODO

# tables to make
    inductor:             inductance, tolerance
    ferrite_bead:         impedance_at_freq, current, resistance
    connector:            series, circuit_configuration, gender, orientation
    transistor_mosfet:    type, vds_max, id_max, power_max, ft
    transistor_jfet:      type, vds_max, idss, power_max, ft
    crystal:              frequency, load_capacitance
    potentiometer:        value, tolerance, power, composition, orientation
    switch:               type, configuration, orientation, current
    relay:                configuration, coil_voltage, coil_current, switch_current
    logic:                function, number_of_units
"""


component_type_registry = []
table_to_component_type = {}
friendly_name_to_component_type = {}


def component(cls):
    """Decorator for component classes. Adds the component to the
    component_type_registry and table_to_component_type and
    friendly_name_to_component_type maps.
    """
    component_type_registry.append(cls)
    table_to_component_type[cls.table] = cls
    friendly_name_to_component_type[cls.friendly_name] = cls
    return cls


def create_component_from_digikey_part(part):
    """Factory to construct the appropriate component type object for a given
    digikey part (API response object).

    Given a Digikey API response object, determines the component type, then
    dispatches to the appropriate Component.from_digikey(part) constructor.

    Args:
        part: Digikey part API response object.

    Returns:
        A `Component` object constructed from the Digikey part details.

    Raises:
        NotImplementedError if the appropriate component type cannot be
        determined.
    """

    for component_type in component_type_registry:
        if component_type.type_matches_digikey_part(part):
            return component_type.from_digikey(part)

    raise NotImplementedError(
        "No component type to handle part type "
        f"'{part.limited_taxonomy.value}' for part "
        f"{part.digi_key_part_number}"
    )


def create_component_from_dict(columns_and_values):
    """Factory to construct the appropriate component type object from a dict
    of column names to column values.

    All appropriate fields for each component type must be present. The type of
    component is determined from the value corresponding to the `IPN` key.

    Args:
        columns_and_values: dict containing all necessary key/value pairs for
            constructing the desired component.

    Returns:
        A `Component` object constructed from the given dict.

    Raises:
        NotImplementedError if the appropriate component type cannot be
        determined.
    """
    IPN = columns_and_values["IPN"]
    for component_type in component_type_registry:
        if component_type.type_matches_IPN(IPN):
            return component_type(**columns_and_values)

    raise NotImplementedError(f"No component type to handle part '{IPN}'")


class Component(ABC):
    primary_key = "IPN"
    true_false_fields = ["exclude_from_bom", "exclude_from_board"]

    def __init__(
        self,
        IPN,
        datasheet,
        description,
        keywords,
        value,
        package,
        kicad_symbol,
        kicad_footprint,
        manufacturer,
        MPN,
        distributor1,
        DPN1,
        distributor2,
        DPN2,
        exclude_from_bom=0,
        exclude_from_board=0,
        **kwargs,
    ):
        # columns that all types of components need. Many of these map onto
        # KiCad builtin fields or properties.
        self.columns = OrderedDict()
        self.columns[self.primary_key] = IPN  # unique ID for component
        self.columns["datasheet"] = datasheet
        self.columns["description"] = description
        self.columns["keywords"] = keywords
        self.columns["value"] = value
        self.columns["package"] = package
        self.columns["exclude_from_bom"] = int(exclude_from_bom)
        self.columns["exclude_from_board"] = int(exclude_from_board)
        self.columns["kicad_symbol"] = kicad_symbol
        self.columns["kicad_footprint"] = kicad_footprint
        self.columns["manufacturer"] = manufacturer
        self.columns["MPN"] = MPN
        self.columns["distributor1"] = distributor1
        self.columns["DPN1"] = DPN1
        self.columns["distributor2"] = distributor2
        self.columns["DPN2"] = DPN2

    def __repr__(self):
        args = [f"\n{k}='{self.columns[k]}'" for k in self.columns]
        return f"{self.__class__.__name__}({','.join(args)})"

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        # compare all columns except IPN
        for col in self.columns:
            if self.columns[col] != other.columns.get(col) and col != self.primary_key:
                return False
        return True

    @classmethod
    def _determine_footprint(cls, data, package):
        """
        Choose a footprint based on the component's parameters, or ask the user
        if there is no known-good footprint.

        Args:
            data:
                dict of data pulled from digikey object. The function will
                store `kicad_footprint` into this dict, and possibly read the
                distributor part number (`DPN1`).
            package:
                string containing a short description of the package, such as
                "32-LQFP (7x7)". This should be a key in the component class's
                kicad_footprint_map dict. If this is not a known package type,
                the user will be prompted to provide a footprint name.
        """
        if package in cls.kicad_footprint_map:
            data["kicad_footprint"] = cls.kicad_footprint_map[package]
        else:
            data["kicad_footprint"] = cls._get_sym_or_fp_from_user(data["DPN1"])

    @staticmethod
    def process_value_with_unit(value):
        """Remove spaces from string (e.g. between value and unit)."""
        return re.sub(r"\s+", "", value)

    @staticmethod
    def process_tolerance(param):
        """Return a processed tolerance string, e.g. 5%, 1.0%, or -."""
        match = re.search(r"\d+\.?\d*", param)
        if match:
            return match.group(0) + "%"
        else:
            # e.g. jumpers have no meaningful tolerance
            return "-"

    @staticmethod
    def process_manufacturer(mfg):
        """Return a short form of the manufacturer's name, if one is known, or
        the full name if no short name is known.
        """
        short_mfg_names = {
            "Amphenol ICC (FCI)": "Amphenol",
        }

        return short_mfg_names.get(mfg, mfg)

    @staticmethod
    def process_smd_package(param):
        """If param contains an SMD package name at the beginning, like 0805,
        return that substring. Otherwise return the original string.
        """
        match = re.match(r"\d\d\d\d", param)
        if match:
            return match.group(0)
        else:
            return param

    @staticmethod
    def _get_sym_or_fp_from_user(PN, fp=True, prompt=True):
        """Prompt user for a library:symbol or library:footprint combination
        for the given symbol or footprint.

        Args:
            PN:
                part number or display name of component. This is displayed to
                the user while asking for a symbol/footprint name, so it should
                probably be the MPN so that the user can look up the part.
            fp: True if prompting for a footprint, False if prompting for a
                symbol.
            prompt: if True, prompt the user for a symbol/footprint. If False,
                don't prompt the user, and return an empty string instead.
        """

        device = "footprint" if fp else "symbol"
        if prompt:
            return input(
                f"Enter {device}_library:{device}_name for " f"component {PN}: "
            )
        else:
            return ""

    @classmethod
    def type_matches_IPN(cls, IPN):
        """Returns true if the component type is appropriate based on the given
        IPN."""
        match = re.match(r"[a-zA-Z]+", IPN)
        part_prefix = match.group() if match else None
        return any(part_prefix == cls_prefix for cls_prefix in cls.IPN_prefix)

    @staticmethod
    @abstractmethod
    def type_matches_digikey_part(digikey_part):
        """Returns true if the component type is appropriate for the provided
        Digikey part."""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_digikey(cls, digikey_part):
        """Construct a component from a digikey part object.

        Returns:
            The constructed component. If the component cannot be constructed
            for any reason, return None.
        """
        raise NotImplementedError

    @classmethod
    def get_digikey_common_data(cls, digikey_part):
        """Return a dict of the common data from a digikey part object."""
        common_data = {
            "datasheet": digikey_part.primary_datasheet,
            "manufacturer": cls.process_manufacturer(digikey_part.manufacturer.value),
            "MPN": digikey_part.manufacturer_part_number,
            "distributor1": "Digikey",
            "DPN1": digikey_part.digi_key_part_number,
            "distributor2": "",
            "DPN2": "",
        }
        return common_data

    def get_create_table_string(self):
        """Return a sqlite string to create a table for the component type."""
        column_defs = [
            column + " PRIMARY KEY" if column == self.primary_key else column
            for column in self.columns.keys()
        ]
        column_defs = ", ".join(column_defs)
        return f"CREATE TABLE IF NOT EXISTS {self.table}({column_defs})"

    def to_sql(self, update=False):
        """Create a SQL command string that will insert the component into the
        database.

        Args:
            update: when True, the generated SQL command will cause duplicate
                rows already in the database to be updated (REPLACE'd) on
                INSERT.  When False, the generated SQL command will not REPLACE
                any existing row with the same key; instead sqlite will
                generate an error.

        Returns:
            A tuple (insert string, column data) of the parameterized SQL
            insert string and the dict of values to populate the insert string
            with.
        """
        column_names = self.columns.keys()
        columns = ",".join(column_names)
        column_keys = ":" + ", :".join(column_names)
        command = "INSERT OR REPLACE" if update else "INSERT"
        insert_string = f"{command} INTO {self.table} ({columns}) VALUES({column_keys})"
        return (insert_string, self.columns)

    def to_csv(self, header=True, body=True):
        """Create a string containing the component data, formatted as CSV.

        Args:
            header: if True, also print a header row containing column names
            body: if True, print the body (values)

        Returns:
            A string containing a CSV representation of the component. If
            `header` is true, the string is a multi-line string containing
            a header row followed by a data row.
        """
        with io.StringIO() as csv_string:
            csvwriter = csv.DictWriter(csv_string, fieldnames=self.columns.keys())
            if header:
                csvwriter.writeheader()
            if body:
                csvwriter.writerow(self.columns)
            return csv_string.getvalue()

    def already_in_db(self, con):
        """Return True if component is already in the database, or False otherwise.

        A component is considered to be in the database if there is a record
        with matching values in all fields except IPN.

        Args:
            con: database connection object.
        Returns: True if comp is in database, otherwise False.
        """
        if self.table not in db.get_table_names(con):
            return False
        cols = [col for col in self.columns.keys() if col != self.primary_key]
        conditions = " AND ".join([f"{col} = :{col}" for col in cols])
        query = f"SELECT 1 FROM {self.table} WHERE {conditions}"
        cur = con.cursor()
        res = cur.execute(query, self.columns).fetchall()
        return bool(res)


@component
class Resistor(Component):
    table = "resistor"
    friendly_name = "Resistor"
    IPN_prefix = ["R"]
    kicad_footprint_map = {
        "0201": "Resistor_SMD:R_0201_0603Metric",
        "0402": "Resistor_SMD:R_0402_1005Metric",
        "0603": "Resistor_SMD:R_0603_1608Metric",
        "0805": "Resistor_SMD:R_0805_2012Metric",
        "1206": "Resistor_SMD:R_1206_3216Metric",
        "1210": "Resistor_SMD:R_1210_3225Metric",
    }

    def __init__(self, resistance, tolerance, power, composition, **kwargs):
        super().__init__(**kwargs)
        self.columns["resistance"] = resistance
        self.columns["tolerance"] = tolerance
        self.columns["power"] = power
        self.columns["composition"] = composition

    @staticmethod
    def process_resistance(param):
        """Return a processed resistance string, e.g. 10 or 1.0K."""
        resistance = re.search(r"\d+\.?\d*\s*[kKmMG]?", param).group(0)
        return re.sub(r"\s", "", re.sub("k", "K", resistance))

    @staticmethod
    def process_power(param):
        """Return a processed power string, e.g. 5W or 0.125W."""
        match = re.search(r"\d+\.?\d*", param)
        if match:
            return match.group(0) + "W"
        else:
            # e.g. jumpers have no meaningful power rating
            return "-"

    @staticmethod
    def process_composition(param):
        """Return a processed composition string, e.g. ThinFilm."""
        return re.sub(" ", "", param)

    @staticmethod
    def make_description(data):
        if data["resistance"] == "0":
            composition = data["composition"].lower()
            data["description"] = f"0Ω jumper, {data['package']}, {composition}"
        else:
            data["description"] = (
                f"{data['resistance']}Ω "
                f"±{data['tolerance']}, "
                f"{data['power']} "
                f"resistor, "
                f"{data['package']}, "
                f"{data['composition'].lower()}"
            )

    @staticmethod
    def make_keywords(data):
        if data["resistance"] == "0":
            data["keywords"] = "jumper"
        else:
            data["keywords"] = f"r res resistor {data['resistance']}"

    @staticmethod
    def type_matches_digikey_part(digikey_part):
        return digikey_part.limited_taxonomy.value == "Resistors"

    @classmethod
    def from_digikey(cls, digikey_part):
        data = cls.get_digikey_common_data(digikey_part)

        for p in digikey_part.parameters:
            if p.parameter == "Resistance":
                data["resistance"] = cls.process_resistance(p.value)
            elif p.parameter == "Tolerance":
                data["tolerance"] = cls.process_tolerance(p.value)
            elif p.parameter == "Power (Watts)":
                data["power"] = cls.process_power(p.value)
            elif p.parameter == "Composition":
                data["composition"] = p.value
            elif p.parameter == "Supplier Device Package":
                data["package"] = p.value

        data["value"] = "${Resistance}"

        cls.make_description(data)
        cls.make_keywords(data)

        data["IPN"] = cls.IPN_prefix[0]
        data["kicad_symbol"] = "Device:R"

        cls._determine_footprint(data, data["package"])

        return cls(**data)


@component
class Capacitor(Component):
    table = "capacitor"
    friendly_name = "Capacitor"
    IPN_prefix = ["C", "CP"]
    kicad_footprint_map = {
        "0201": "Capacitor_SMD:C_0201_0603Metric",
        "0402": "Capacitor_SMD:C_0402_1005Metric",
        "0603": "Capacitor_SMD:C_0603_1608Metric",
        "0805": "Capacitor_SMD:C_0805_2012Metric",
        "1206": "Capacitor_SMD:C_1206_3216Metric",
        "1210": "Capacitor_SMD:C_1210_3225Metric",
    }

    def __init__(self, capacitance, tolerance, voltage, dielectric, **kwargs):
        super().__init__(**kwargs)
        self.columns["capacitance"] = capacitance
        self.columns["tolerance"] = tolerance
        self.columns["voltage"] = voltage
        self.columns["dielectric"] = dielectric

    @staticmethod
    def process_capacitance(param):
        """Return a processed capacitance string, normalized between 1 and 999,
        e.g. 10nF or 1.0uF.
        """
        # regex includes both unicode mu and micro symbols
        result = re.search(r"(\d+\.?\d*)\s*([fpPnNuUμµmM]?)", param)
        value = float(result.group(1))
        si_prefix = result.group(2)
        si_prefix = re.sub(r"[uUμµ]", "μ", si_prefix)
        si_prefix = re.sub(r"P", "p", si_prefix)
        si_prefix = re.sub(r"N", "n", si_prefix)
        si_prefix = re.sub(r"M", "m", si_prefix)

        prefixes = ["f", "p", "n", "μ", "m"]
        n = prefixes.index(si_prefix)
        while value < 1 and n > 0:
            # need to go down a level
            value *= 1000
            n -= 1
            si_prefix = prefixes[n]
        while value >= 1000 and n < len(prefixes) - 1:
            # need to go up a level
            value /= 1000
            n += 1
            si_prefix = prefixes[n]

        value = str(value).rstrip("0").rstrip(".")
        return value + si_prefix + "F"

    @staticmethod
    def process_voltage(param):
        """Return a processed voltage rating string, e.g. 50V."""
        match = re.search(r"\d+\.?\d*", param)
        return match.group(0) + "V"

    @staticmethod
    def process_polarization(param):
        """Return a polarization string, either 'Polarized' or 'Unpolarized'."""
        if param == "Bi-Polar":
            return "Unpolarized"
        elif param == "Polar":
            return "Polarized"
        else:
            raise ValueError(f"Unknown capacitor polarization '{param}'.")

    @staticmethod
    def process_dimension(param):
        """Return a dimension string in mm, with 3 digits, e.g. 5.00mm or
        12.7mm.
        """
        match = re.search(r"(\d+\.?\d*)\s*mm", param)
        try:
            dim = float(match.group(1))
            return f"{dim:0<4}mm"
        except AttributeError:
            return "-"

    @staticmethod
    def _determine_symbol(polarization):
        """Choose an appropriate capacitor symbol.

        Args:
            polarization:
                "Polarized" or "Unpolarized".
        Returns:
            String containing the symbol library and name ("lib:symbol")
        """
        if polarization == "Unpolarized":
            return "Device:C"
        else:
            return "Device:C_Polarized_US"

    @classmethod
    def _determine_footprint(cls, data, polarization, dimensions):
        """
        Choose a footprint based on the component's parameters, or ask the user
        if there is no known-good footprint.

        Args:
            data:
                dict of data pulled from digikey object. The function will
                store `kicad_footprint` into this dict.
            polarization:
                "Polarized" or "Unpolarized".
            dimensions:
                dict of dimension name to (string) dimensions, such as
                "diameter": "5.00mm". Different types of capacitors require
                different types of dimensions.
        Returns:
            None, if a footprint could not be determined.
            tuple of package_short (e.g. "0805" or "Radial") and package_dims
            (e.g. "" or "D5.00mm_H10.0mm_P2.00mm")
        """

        package_short = ""
        package_dims = ""
        if data["package"] in cls.kicad_footprint_map:
            data["kicad_footprint"] = cls.kicad_footprint_map[data["package"]]
            package_short = data["package"]
        else:
            data["kicad_footprint"] = cls._get_sym_or_fp_from_user(data["DPN1"])
            pol = "P" if polarization == "Polarized" else ""
            try:
                diameter = dimensions["diameter"]
                height = dimensions["height"]
                pitch = dimensions["pitch"]
            except KeyError:
                print_error("unknown package dimensions: {e}")
                return None
            if data["package"] == "Radial, Can":
                package_short = "Radial"
                package_dims = f"D{diameter}_H{height}_P{pitch}"
            elif data["package"] == "Radial, Can - SMD":
                package_short = "Radial_SMD"
                package_dims = f"D{diameter}_H{height}"
            data["package"] = f"C{pol}_{package_short}_{package_dims}"

        return package_short, package_dims

    @classmethod
    def _determine_metadata(cls, data, polarization, package_short, package_dims):
        """Create an IPN, description, and keywords for the component.

        Args:
            data:
                dict of data pulled from digikey object. The function will
                store `IPN`, `description`, and `keywords` into this dict.
            polarization:
                "Polarized" or "Unpolarized".
            package_short:
                short description of package, e.g. "8085" or "Radial".
            package_dims:
                short dimension string of package, which can be blank, e.g.
                "" or "D5.00mm_H10.0mm_P2.00mm".
        """
        data["IPN"] = cls.IPN_prefix[0]
        dielectric = data["dielectric"]
        if "olarized" in dielectric:  # don't lowercase dielectrics like X7R
            dielectric = dielectric.lower()
        data["description"] = (
            f"{data['capacitance']} "
            f"±{data['tolerance']}, "
            f"{data['voltage']}, "
            f"{dielectric} "
            f"capacitor, "
            f"{package_short.lower()}"
        )
        if package_dims:
            dims = (
                package_dims.replace("D", "diameter ")
                .replace("H", "height ")
                .replace("P", "pitch ")
                .replace("_", " ")
            )
            data["description"] += f", {dims}"
        data["keywords"] = (
            f"c cap capacitor " f"{polarization.lower()} {data['capacitance']}"
        )

    @staticmethod
    def type_matches_digikey_part(digikey_part):
        return digikey_part.limited_taxonomy.value == "Capacitors"

    @classmethod
    def from_digikey(cls, digikey_part):
        data = cls.get_digikey_common_data(digikey_part)

        dimensions = {}
        for p in digikey_part.parameters:
            if p.parameter == "Capacitance":
                data["capacitance"] = cls.process_capacitance(p.value)
            elif p.parameter == "Tolerance":
                data["tolerance"] = cls.process_tolerance(p.value)
            elif p.parameter == "Voltage - Rated":
                data["voltage"] = cls.process_voltage(p.value)
            elif p.parameter == "Temperature Coefficient":
                data["dielectric"] = p.value
            elif p.parameter == "Package / Case":
                data["package"] = cls.process_smd_package(p.value)
            elif p.parameter == "Polarization":
                polarization = cls.process_polarization(p.value)
            elif p.parameter == "Lead Spacing":
                dimensions["pitch"] = cls.process_dimension(p.value)
            elif p.parameter == "Size / Dimension":
                dimensions["diameter"] = cls.process_dimension(p.value)
            elif p.parameter == "Height - Seated (Max)":
                dimensions["height"] = cls.process_dimension(p.value)

        family = digikey_part.family.value
        if family == "Ceramic Capacitors":
            polarization = "Unpolarized"
        elif family == "Aluminum Electrolytic Capacitors":
            data["dielectric"] = f"{polarization} Electrolytic"
        else:
            print_error(f"capacitor family '{family}' is not implemented")
            return None

        data["value"] = "${Capacitance}"
        data["kicad_symbol"] = cls._determine_symbol(polarization)

        package_data = cls._determine_footprint(data, polarization, dimensions)
        if package_data:
            package_short, package_dims = package_data
        else:
            return None

        cls._determine_metadata(data, polarization, package_short, package_dims)

        return cls(**data)


@component
class OpAmp(Component):
    table = "opamp"
    friendly_name = "Op Amp"
    IPN_prefix = ["OPAMP"]
    kicad_footprint_map = {
        '8-SOIC (0.154", 3.90mm Width)': "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    }

    def __init__(self, bandwidth, num_units, **kwargs):
        super().__init__(**kwargs)
        self.columns["bandwidth"] = bandwidth
        self.columns["num_units"] = num_units

    @staticmethod
    def type_matches_digikey_part(digikey_part):
        part_type = digikey_part.limited_taxonomy.value
        sub_type = digikey_part.limited_taxonomy.children[0].value
        return part_type == "Integrated Circuits (ICs)" and "OP Amps" in sub_type

    @classmethod
    def from_digikey(cls, digikey_part):
        data = cls.get_digikey_common_data(digikey_part)

        for p in digikey_part.parameters:
            if p.parameter == "Gain Bandwidth Product":
                data["bandwidth"] = p.value
            elif p.parameter == "Slew Rate":
                slewrate = p.value
            elif p.parameter == "Package / Case":
                data["package"] = p.value
            elif p.parameter == "Supplier Device Package":
                short_package = p.value
            elif p.parameter == "Number of Circuits":
                data["num_units"] = p.value

        data["value"] = "${MPN}"
        data["keywords"] = "amplifier op amp"

        num_unit_map = {"1": "Single", "2": "Dual", "4": "Quad"}
        data["description"] = (
            f"{num_unit_map[data['num_units']]} "
            f"{data['bandwidth']}, {slewrate} opamp, {short_package}"
        )
        IPN = cls.IPN_prefix[0]
        data["IPN"] = re.sub(r"\s+", "", IPN)

        data["kicad_symbol"] = cls._get_sym_or_fp_from_user(data["DPN1"], fp=False)

        cls._determine_footprint(data, data["package"])

        return cls(**data)


@component
class Microcontroller(Component):
    table = "microcontroller"
    friendly_name = "Microcontroller"
    IPN_prefix = ["MCU"]
    kicad_footprint_map = {
        "8-SOIC": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        "14-TSSOP": "Package_SO:TSSOP-14_4.4x5mm_P0.65mm",
        "20-TSSOP": "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm",
        "32-LQFP (7x7)": "Package_QFP:LQFP-32_7x7mm_P0.8mm",
        "48-LQFP (7x7)": "Package_QFP:LQFP-48_7x7mm_P0.5mm",
        "64-LQFP (10x10)": "Package_QFP:LQFP-64_10x10mm_P0.5mm",
        "80-LQFP (12x12)": "Package_QFP:LQFP-80_12x12mm_P0.5mm",
        "80-LQFP (14x14)": "Package_QFP:LQFP-80_14x14mm_P0.65mm",
        "100-LQFP (14x14)": "Package_QFP:LQFP-100_14x14mm_P0.5mm",
        "128-LQFP (14x14)": "Package_QFP:LQFP-128_14x14mm_P0.4mm",
        "144-LQFP (20x20)": "Package_QFP:LQFP-144_20x20mm_P0.5mm",
        "176-LQFP (24x24)": "Package_QFP:LQFP-176_24x24mm_P0.5mm",
        "208-LQFP (28x28)": "Package_QFP:LQFP-208_28x28mm_P0.5mm",
        "20-UFQFPN (3x3)": "Package_DFN_QFN:ST_UFQFPN-20_3x3mm_P0.5mm",
        "28-UFQFPN (4x4)": "Package_DFN_QFN:QFN-28_4x4mm_P0.5mm",
        "32-UFQFPN (5x5)": "Package_DFN_QFN:QFN-32-1EP_5x5mm_P0.5mm_EP3.45x3.45mm",
        "36-VFQFPN (6x6)": "Package_DFN_QFN:QFN-36-1EP_6x6mm_P0.5mm_EP4.1x4.1mm",
        "48-UFQFPN (7x7)": "Package_DFN_QFN:QFN-48-1EP_7x7mm_P0.5mm_EP5.6x5.6mm",
        "68-VFQFPN (8x8)": "Package_DFN_QFN:QFN-68-1EP_8x8mm_P0.4mm_EP6.4x6.4mm",
    }

    def __init__(self, speed, core, **kwargs):
        super().__init__(**kwargs)
        self.columns["speed"] = speed
        self.columns["core"] = core

    @staticmethod
    def process_pincount(package):
        """Extract pincount from a package name, e.g. "32" from "32-LQFP"."""
        pincount_match = re.match(r"^\d*", package)
        return pincount_match.group(0) if pincount_match else ""

    @staticmethod
    def process_core(param):
        """Return a sanitized core name, removing any characters that aren't
        alphanumeric, underscores, dashes, or spaces (for example, ® or ™).
        """
        return re.sub(r"[^\d\w \-]", "", param)

    @staticmethod
    def type_matches_digikey_part(digikey_part):
        part_type = digikey_part.limited_taxonomy.value
        sub_type = digikey_part.limited_taxonomy.children[0].value
        return (
            part_type == "Integrated Circuits (ICs)" and "Microcontrollers" in sub_type
        )

    @classmethod
    def from_digikey(cls, digikey_part):
        data = cls.get_digikey_common_data(digikey_part)

        for p in digikey_part.parameters:
            if p.parameter == "Supplier Device Package":
                data["package"] = p.value
                pincount = cls.process_pincount(data["package"])
            elif p.parameter == "Core Processor":
                data["core"] = cls.process_core(p.value)
            elif p.parameter == "Speed":
                data["speed"] = p.value

        data["value"] = "${MPN}"
        data["keywords"] = "mcu microcontroller uc"
        data["description"] = (
            f"{pincount} pin "
            f"{data['core']} MCU, "
            f"{data['speed']}, "
            f"{data['package']}"
        )
        data["IPN"] = cls.IPN_prefix[0]

        data["kicad_symbol"] = cls._get_sym_or_fp_from_user(data["DPN1"], fp=False)
        cls._determine_footprint(data, data["package"])

        return cls(**data)


@component
class VoltageRegulator(Component):
    table = "voltage_regulator"
    friendly_name = "Voltage Regulator"
    IPN_prefix = ["VREG"]
    kicad_footprint_map = {
        "TO-220-3": "Package_TO_SOT_THT:TO-220-3_Vertical",
    }

    def __init__(self, voltage, current, **kwargs):
        super().__init__(**kwargs)
        self.columns["voltage"] = voltage
        self.columns["current"] = current

    @staticmethod
    def type_matches_digikey_part(digikey_part):
        part_type = digikey_part.limited_taxonomy.value
        sub_type = digikey_part.limited_taxonomy.children[0].value
        return (
            part_type == "Integrated Circuits (ICs)"
            and "Voltage Regulators" in sub_type
        )

    @classmethod
    def from_digikey(cls, digikey_part):
        data = cls.get_digikey_common_data(digikey_part)

        for p in digikey_part.parameters:
            if p.parameter == "Supplier Device Package":
                data["package"] = p.value
            elif p.parameter == "Voltage - Input (Max)":
                vin_max = p.value
            elif p.parameter == "Voltage - Output (Min/Fixed)":
                vout_min = p.value
            elif p.parameter == "Voltage - Output (Max)":
                vout_max = p.value
            elif p.parameter == "Current - Output":
                data["current"] = p.value
            elif p.parameter == "Output Type":
                if p.value == "Fixed":
                    output_type = "fixed"
                else:
                    output_type = "adjustable"

        data["value"] = "${MPN}"
        data["keywords"] = "voltage regulator vreg"
        if output_type == "fixed":
            data["voltage"] = vout_min
        else:
            data["voltage"] = f"{vout_min} - {vout_max}"
        data["description"] = (
            f"{data['manufacturer']} {data['MPN']}, "
            f"{data['voltage']} @{data['current']} out, "
            f"{vin_max} in, "
            f"{output_type} voltage regulator, "
            f"{data['package']}"
        )
        IPN = cls.IPN_prefix[0]
        data["IPN"] = re.sub(r"\s+", "", IPN)

        data["kicad_symbol"] = cls._get_sym_or_fp_from_user(data["DPN1"], fp=False)
        cls._determine_footprint(data, data["package"])

        return cls(**data)


@component
class Diode(Component):
    table = "diode"
    friendly_name = "Diode"
    IPN_prefix = ["D"]
    kicad_footprint_map = {
        "DO-35": "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal",
        "SOD-123": "Diode_SMD:D_SOD-123",
        "SOD-323": "Diode_SMD:D_SOD-323",
        "SOT-23": "Package_TO_SOT_SMD:SOT-23",
    }

    def __init__(
        self,
        diode_type,
        reverse_voltage,
        current_or_power,
        diode_configuration,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.columns["diode_type"] = diode_type
        self.columns["reverse_voltage"] = reverse_voltage
        self.columns["current_or_power"] = current_or_power
        self.columns["diode_configuration"] = diode_configuration

    @staticmethod
    def type_matches_digikey_part(digikey_part):
        part_type = digikey_part.limited_taxonomy.value
        sub_type = digikey_part.limited_taxonomy.children[0].value
        return part_type == "Discrete Semiconductor Products" and (
            "Diodes - Rectifiers" in sub_type or "Diodes - Zener" in sub_type
        )

    @classmethod
    def from_digikey(cls, digikey_part):
        data = cls.get_digikey_common_data(digikey_part)

        for p in digikey_part.parameters:
            if p.parameter == "Supplier Device Package":
                data["package"] = p.value
            elif p.parameter == "Technology":
                data["diode_type"] = p.value.lower()
            elif p.parameter == "Voltage - DC Reverse (Vr) (Max)":
                data["reverse_voltage"] = cls.process_value_with_unit(p.value)
            elif p.parameter in (
                "Current - Average Rectified (Io)",
                "Power - Max",
                "Current - Average Rectified (Io) (per Diode)",
            ):
                data["current_or_power"] = cls.process_value_with_unit(p.value)
            elif p.parameter == "Voltage - Zener (Nom) (Vz)":
                data["reverse_voltage"] = cls.process_value_with_unit(p.value)
                data["diode_type"] = "zener"
            elif p.parameter == "Diode Configuration":
                data["diode_configuration"] = p.value.lower()

        data["value"] = "${MPN}"
        data["keywords"] = "diode"
        data["description"] = (
            f"{data['reverse_voltage']}, {data['current_or_power']} "
            f"{data['diode_type']} diode, "
        )
        if "diode_configuration" in data:
            data["description"] += f"{data['diode_configuration']}, "
            data["keywords"] += " array"
        data["description"] += f"{data['package']}"
        data["IPN"] = cls.IPN_prefix[0]

        kicad_symbol_map = {
            "standard": "Device:D",
            "schottky": "Device:D_Schottky",
            "zener": "Device:D_Zener",
        }
        if "diode_configuration" not in data and data["diode_type"] in kicad_symbol_map:
            data["kicad_symbol"] = kicad_symbol_map[data["diode_type"]]
        else:
            data["kicad_symbol"] = cls._get_sym_or_fp_from_user(data["DPN1"], fp=False)
        cls._determine_footprint(data, data["package"])

        if "diode_configuration" not in data:
            data["diode_configuration"] = ""

        return cls(**data)


@component
class LED(Component):
    table = "led"
    friendly_name = "LED"
    IPN_prefix = ["LED"]
    kicad_footprint_map = {
        "0603": "LED_SMD:LED_0603_1608Metric",
        "5mm": "LED_THT:LED_D5.0mm",
    }

    def __init__(self, color, forward_voltage, diode_configuration, **kwargs):
        super().__init__(**kwargs)
        self.columns["color"] = color
        self.columns["forward_voltage"] = forward_voltage
        self.columns["diode_configuration"] = diode_configuration

    @staticmethod
    def process_led_package(param):
        """Return a sanitized LED package name.

        Long SMD package names are transformed to their short form (e.g.
        "0603 (1608 Metric)" becomes "0603"), and some other common package
        names are made friendlier (e.g. "T-1 3/4" becomes "5mm"). If no
        transformation is applicable, the original package name is returned.

        This relies partially on a lookup table of known package name
        transformations.
        """
        package_map = {
            "T-1 3/4": "5mm",
        }
        mod_package = super(LED, LED).process_smd_package(param)
        if mod_package != param:
            return mod_package
        elif param in package_map:
            return package_map[param]
        else:
            return param

    @staticmethod
    def process_led_color(param):
        """Return a sanitized LED color."""
        # remove "(RGB)", if present
        short_color = re.sub(r" \(.*\)", "", param)
        # remove commas and spaces
        short_color = re.sub(r"[, ]+", "", short_color)
        return short_color

    @staticmethod
    def process_led_dimension(param):
        """Return a dimension string in mm, with 1 digit after each decimal
        point, e.g. "5.0x5.0mm" from "5.00mm L x 5.00mm W".
        """
        dim_string = r"(\d+\.?\d*)"
        match = re.search(rf"{dim_string}[\smLW]*x" rf"\s*{dim_string}\s*mm", param)
        try:
            dim1 = float(match.group(1))
            dim2 = float(match.group(2))
            return f"{dim1:.1f}x{dim2:.1f}mm"
        except AttributeError:
            return "-"

    @classmethod
    def _determine_footprint(cls, data, package):
        """Determine footprint based on package name and other component data.

        If package cannot be determined, prompt the user. For LEDs
        specifically, only attempt to auto-determine footprints for
        single-color LEDs.
        """

        if data["diode_configuration"] == "":
            super()._determine_footprint(data, package)
        else:
            data["kicad_footprint"] = cls._get_sym_or_fp_from_user(data["DPN1"])

    @staticmethod
    def type_matches_digikey_part(digikey_part):
        return digikey_part.limited_taxonomy.value == "Optoelectronics"

    @classmethod
    def from_digikey(cls, digikey_part):
        data = cls.get_digikey_common_data(digikey_part)

        addressable = False
        for p in digikey_part.parameters:
            if p.parameter == "Package / Case":
                data["package"] = cls.process_led_package(p.value)
            elif p.parameter == "Supplier Device Package":
                supplier_device_package = cls.process_led_package(p.value)
            elif p.parameter == "Size / Dimension":
                size_dimension = p.value
            elif p.parameter == "Color":
                data["color"] = p.value
            elif p.parameter == "Voltage - Forward (Vf) (Typ)":
                data["forward_voltage"] = p.value
            elif p.parameter == "Interface":
                addressable = True
            elif p.parameter == "Configuration":
                if p.value == "Standard" or p.value == "Discrete":
                    data["diode_configuration"] = ""
                else:
                    data["diode_configuration"] = p.value

        if "package" not in data:
            data["package"] = cls.process_led_dimension(size_dimension)
        if "forward_voltage" not in data:
            data["forward_voltage"] = ""
        if data["package"] == "Radial - 4 Leads":
            data["package"] = supplier_device_package

        data["value"] = "${Color}"
        data["keywords"] = "led"
        data["IPN"] = cls.IPN_prefix[0]
        data["description"] = f"{data['color']} "
        if addressable:
            data["description"] += "addressable "
        data["description"] += "LED, "
        if data["diode_configuration"]:
            data["description"] += f"{data['diode_configuration'].lower()}, "
        data["description"] += f"{data['package']}"

        if data["diode_configuration"] == "" and not addressable:
            data["kicad_symbol"] = "Device:LED"
        else:
            data["kicad_symbol"] = cls._get_sym_or_fp_from_user(data["DPN1"], fp=False)
        cls._determine_footprint(data, data["package"])

        return cls(**data)


@component
class BJT(Component):
    table = "transistor_bjt"
    friendly_name = "BJT"
    IPN_prefix = ["NPN", "PNP"]
    kicad_footprint_map = {
        "TO-92-3": "Package_TO_SOT_THT:TO-92_Inline",
    }

    def __init__(self, bjt_type, vce_max, ic_max, power_max, ft, **kwargs):
        super().__init__(**kwargs)
        self.columns["bjt_type"] = bjt_type
        self.columns["vce_max"] = vce_max
        self.columns["ic_max"] = ic_max
        self.columns["power_max"] = power_max
        self.columns["ft"] = ft

    @staticmethod
    def process_transistor_type(param):
        """Process a Digikey part's "Transistor Type" parameter into a simpler
        string, e.g. "NPN" for a transistor type of "NPN" or "4xNPN" for a quad
        NPN array with transistor type "4 NPN (Quad)".

        Also determines whether or not the "Transistor Type" represents a
        transistor array.

        Returns:
            Tuple of transistor type string, transistor array bool

        """
        m = re.match(r"(\d*)\s*(NPN|PNP)[,\s]*(\d*)\s*(NPN|PNP)?", param)
        s = ""
        array = False
        if m.group(2):  # NPN|PNP
            if m.group(1):  # number of units
                array = True
                s += f"{m.group(1)}x"
            s += m.group(2)
        if m.group(4):  # second NPN|PNP
            array = True
            s += "-"
            if m.group(3):  # number of units
                s += f"{m.group(3)}x"
            s += f"{m.group(4)}"
        return s, array

    @staticmethod
    def type_matches_digikey_part(digikey_part):
        part_type = digikey_part.limited_taxonomy.value
        sub_type = digikey_part.limited_taxonomy.children[0].value
        return (
            part_type == "Discrete Semiconductor Products"
            and "Bipolar (BJT)" in sub_type
        )

    @classmethod
    def from_digikey(cls, digikey_part):
        data = cls.get_digikey_common_data(digikey_part)

        for p in digikey_part.parameters:
            if p.parameter == "Transistor Type":
                data["bjt_type"], array = cls.process_transistor_type(p.value)
                npn_or_pnp = "npn" if "NPN" in p.value else "pnp"
            elif p.parameter == "Voltage - Collector Emitter Breakdown (Max)":
                data["vce_max"] = cls.process_value_with_unit(p.value)
            elif p.parameter == "Current - Collector (Ic) (Max)":
                data["ic_max"] = cls.process_value_with_unit(p.value)
            elif p.parameter == "Power - Max":
                data["power_max"] = cls.process_value_with_unit(p.value)
            elif p.parameter == "Frequency - Transition":
                data["ft"] = cls.process_value_with_unit(p.value)
            elif p.parameter == "Supplier Device Package":
                data["package"] = p.value

        data["value"] = "${MPN}"
        data["keywords"] = f"bjt transistor {npn_or_pnp}"
        if npn_or_pnp == "npn":
            data["IPN"] = cls.IPN_prefix[0]
        else:
            data["IPN"] = cls.IPN_prefix[1]
        array_string = " array" if array else ""
        data["description"] = (
            f"{data['ic_max']} Ic, "
            f"{data['vce_max']} Vce, "
            f"{data['power_max']}, "
            f"{data['ft']} "
            f"{data['bjt_type']} BJT{array_string}, "
            f"{data['package']}"
        )
        data["kicad_symbol"] = cls._get_sym_or_fp_from_user(data["DPN1"], fp=False)
        data["kicad_footprint"] = cls._get_sym_or_fp_from_user(data["DPN1"])

        return cls(**data)


@component
class Connector(Component):
    table = "connector"
    friendly_name = "Connector"
    IPN_prefix = ["CONN"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @staticmethod
    def type_matches_digikey_part(digikey_part):
        part_type = digikey_part.limited_taxonomy.value
        return part_type == "Connectors, Interconnects"

    @classmethod
    def from_digikey(cls, digikey_part):
        data = cls.get_digikey_common_data(digikey_part)

        positions = ""
        rows = ""
        mounting_type = ""
        orientation = ""
        connector_type = ""
        contact_type = ""
        pitch = ""
        shrouded = ""
        latch = ""
        polarization = ""
        diameter = ""
        signal_lines = ""
        switch = ""
        for p in digikey_part.parameters:
            if p.parameter == "Number of Positions":
                positions = p.value
            elif p.parameter == "Number of Rows":
                rows = p.value
            elif p.parameter == "Mounting Type":
                if "Through Hole" in p.value:
                    mounting_type = "Through Hole"
                elif "Surface Mount" in p.value:
                    mounting_type = "Surface Mount"
                else:
                    mounting_type = "unknown mounting type"
                if "Right Angle" in p.value:
                    orientation = "Horizontal"
                else:
                    orientation = "Vertical"
            elif p.parameter == "Pitch - Mating":
                if '0.100"' in p.value:
                    pitch = "2.54mm"
                else:
                    pitch = p.value
            elif p.parameter == "Shrouding":
                if "unshrouded" in p.value.lower():
                    shrouded = "Unshrouded"
                elif "shrouded" in p.value.lower():
                    shrouded = "Shrouded"
                else:
                    shrouded = ""
            elif p.parameter == "Industry Recognized Mating Diameter":
                if "3.50mm" in p.value:
                    diameter = "3.5mm"
                elif "6.35mm" in p.value:
                    diameter = "6.35mm"
                elif "2.50mm" in p.value:
                    diameter = "2.5mm"
                else:
                    diameter = p.value
            elif p.parameter == "Connector Type":
                if "header" in p.value.lower():
                    connector_type = "Header"
                else:
                    connector_type = p.value
            elif p.parameter == "Contact Type":
                if "female" in p.value.lower():
                    contact_type = "Sockets"
                elif "male" in p.value.lower():
                    contact_type = "Pins"
                else:
                    contact_type = ""
            elif p.parameter == "Fastening Type":
                if "Latch" in p.value:
                    latch = "Latch"
                else:
                    latch = ""
            elif p.parameter == "Features":
                if "Polarizing Key" in p.value:
                    polarization = "Polarizing Key"
                else:
                    polarization = ""
            elif p.parameter == "Signal Lines":
                signal_lines = p.value
            elif p.parameter == "Internal Switch":
                switch = p.value

        series = digikey_part.series.value

        data["IPN"] = cls.IPN_prefix[0]
        data["package"] = connector_type
        description = ""
        if data["manufacturer"]:
            description += f"{data['manufacturer']} "
        if series and series != "-":
            description += f"{series} "
        if positions and rows:
            cols = int(int(positions) / int(rows))
            description += f"{rows}x{cols:02} "
        if shrouded:
            description += f"{shrouded} "
        if diameter:
            description += f"{diameter} "
        description += f"{connector_type}, "
        if contact_type:
            description += f"{contact_type}, "
        if pitch:
            description += f"{pitch}, "
        description += f"{mounting_type}, {orientation}"
        if latch:
            description += f", {latch}"
        if polarization:
            description += f", {polarization}"
        if signal_lines:
            description += f", {signal_lines}"
        if switch:
            description += f", {switch}"
        data["description"] = description
        data["keywords"] = ""
        data["value"] = "${MPN}"
        data["kicad_symbol"] = cls._get_sym_or_fp_from_user(data["DPN1"], fp=False)
        data["kicad_footprint"] = cls._get_sym_or_fp_from_user(data["DPN1"])

        return cls(**data)


@component
class Comparator(Component):
    table = "comparator"
    friendly_name = "Comparator"
    IPN_prefix = ["COMP"]
    kicad_footprint_map = {
        '8-SOIC (0.154", 3.90mm Width)': "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    }

    def __init__(self, output, num_units, **kwargs):
        super().__init__(**kwargs)
        self.columns["output"] = output
        self.columns["num_units"] = num_units

    @staticmethod
    def type_matches_digikey_part(digikey_part):
        part_type = digikey_part.limited_taxonomy.value
        sub_type = digikey_part.limited_taxonomy.children[0].value
        return part_type == "Integrated Circuits (ICs)" and "Comparators" in sub_type

    @classmethod
    def from_digikey(cls, digikey_part):
        data = cls.get_digikey_common_data(digikey_part)

        for p in digikey_part.parameters:
            if p.parameter == "Output Type":
                if "Open-Collector" in p.value:
                    data["output"] = "Open-Collector"
                elif "Push-Pull" in p.value:
                    data["output"] = "Push-Pull"
                else:
                    data["output"] = p.value
            elif p.parameter == "Package / Case":
                data["package"] = p.value
            elif p.parameter == "Supplier Device Package":
                short_package = p.value
            elif p.parameter == "Number of Elements":
                data["num_units"] = p.value

        data["value"] = "${MPN}"
        data["keywords"] = "comparator"

        num_unit_map = {"1": "Single", "2": "Dual", "4": "Quad"}
        data["description"] = (
            f"{num_unit_map[data['num_units']]} comparator, "
            f"{data['output'].lower()} output, {short_package}"
        )
        IPN = cls.IPN_prefix[0]
        data["IPN"] = re.sub(r"\s+", "", IPN)

        data["kicad_symbol"] = cls._get_sym_or_fp_from_user(data["DPN1"], fp=False)

        cls._determine_footprint(data, data["package"])

        return cls(**data)


@component
class Switch(Component):
    table = "switch"
    friendly_name = "Switch"
    IPN_prefix = ["SW", "BUT"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @staticmethod
    def type_matches_digikey_part(digikey_part):
        part_type = digikey_part.limited_taxonomy.value
        return part_type == "Switches"

    @classmethod
    def from_digikey(cls, digikey_part):
        data = cls.get_digikey_common_data(digikey_part)

        for p in digikey_part.parameters:
            if p.parameter == "Circuit":
                data["circuit"] = p.value
            elif p.parameter == "Switch Function":
                data["switch_function"] = p.value
            elif p.parameter == "Mounting Type":
                data["mounting"] = p.value

        series = digikey_part.series.value
        sub_type = digikey_part.limited_taxonomy.children[0].value

        if sub_type == "Tactile Switches":
            data["IPN"] = cls.IPN_prefix[1]
        else:
            data["IPN"] = cls.IPN_prefix[0]
        data["IPN"] = cls.IPN_prefix[0]
        data["package"] = series
        description = f"{data['manufacturer']} {series}"
        if sub_type == "Tactile Switches":
            description += " tactile switch, "
        else:
            description += " switch, "
        description += f"{data['circuit']}"
        data["description"] = description
        if sub_type == "Tactile Switches":
            data["keywords"] = "button push"
        else:
            data["keywords"] = ""

        data["value"] = "${MPN}"
        data["kicad_symbol"] = cls._get_sym_or_fp_from_user(data["DPN1"], fp=False)
        data["kicad_footprint"] = cls._get_sym_or_fp_from_user(data["DPN1"])

        return cls(**data)


@component
class Graphic(Component):
    table = "graphic"
    friendly_name = "Graphic"
    IPN_prefix = ["GRAPHIC"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @staticmethod
    def type_matches_digikey_part(digikey_part):
        return False  # graphics never come from digikey parts

    @classmethod
    def from_digikey(cls, digikey_part):
        raise NotImplementedError(
            "Graphic components cannot be made from Digikey parts"
        )
