from pathlib import Path
import numpy as np

from rich.panel import Panel
from rich.text import Text
from rich.console import Group, Console
from rich.padding import Padding
from rich.traceback import install as install_rich_tracebacks

from harvesters.core import Harvester, DeviceInfo, ImageAcquirer, Buffer, Component2DImage, NodeMap, ParameterSet
from genicam.genapi import (
    ICategory,
    ICommand,
    IInteger,
    IEnumeration,
    IString,
    IBoolean,
    IDeviceInfo,
    IFloat,
    IValue,
    IRegister,
    IEnumEntry,
    EIncMode,
    ERepresentation,
    EDisplayNotation,
    EAccessMode,
    AccessException,
)

from genicam.gentl import AccessDeniedException

from typing import Dict, Any, Callable, Optional
import sys

install_rich_tracebacks(show_locals=True)

# download latest GenTL producer .exe from http://static.matrix-vision.com/mvIMPACT_Acquire/
# install, and find it in C:\Program Files\Balluff\ImpactAcquire\bin\x64

IMPACT_ACQUIRE_LOCATIONS = ["C:/Program Files/Balluff", "C:/Program Files/MATRIX VISION"]
IMPACT_PATH_TO_CTI = "ImpactAcquire/bin/x64/mvGenTLProducer.cti"


class CameraDriver(Harvester):

    def __init__(self, *args, verbose=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.verbose = verbose

    def __enter__(self):
        self = super().__enter__()
        self.get_genicam_driver_location()  # finds the proper genicam driver.
        # Needs to be installed, if not installed will provide a usefull message
        self.update()  # update devices infos
        return self

    def get_genicam_driver_location(self) -> None:

        cti_locations = [Path(install_location) / IMPACT_PATH_TO_CTI for install_location in IMPACT_ACQUIRE_LOCATIONS]

        for cti_file in cti_locations:
            if cti_file.exists:
                if self.verbose:
                    console = Console()
                    console.print(
                        Text.assemble(
                            ("💽 ImpactAcquire driver loading success", "bright_green"),
                            (": Found a .cti file at ", "grey23"),
                            (f"{cti_file}", "reverse grey23"),
                        )
                    )
                return self.add_file(str(cti_file), check_existence=True, check_validity=True)

        # if no file is found, we return an usefull error
        raise ValueError(
            "Didn't found an installation of ImpactAcquire. Please download and install one. "
            "You can find it at this link : http://static.matrix-vision.com/mvIMPACT_Acquire/ "
            "Prefer using the lastest version. Once you clicked on it, select an executeable for your "
            "operating system (most likely ImpactAcquire-x86_64-X.X.X.exe "
            "if you are on a 64bit Windows computer). This package will then try to look for .cti files at "
            f"either of these locations : {', '.join([str(file) for file in cti_locations])}. "
            " Please make sure it exists into one of these locations if the error persists."
        )

    def check_cameras(self) -> Dict[str, DeviceInfo]:

        console = Console()
        cameras = {}

        if not self.device_info_list:
            console.print(
                "No device or camera is available. Check that you properly connected "
                "them and that they are powered on",
                style="bright_red",
            )
            return cameras

        property_style = "dark_slate_gray2"
        devices_infos = []
        for device in self.device_info_list:
            device_properties = device.property_dict

            cameras[device_properties["id_"]] = device

            if self.verbose:
                device_infos = Panel(
                    Text.assemble(
                        ("Model: ", property_style),
                        device_properties["model"],
                        ("\nSerial number: ", property_style),
                        device_properties["serial_number"],
                        ("\nID: ", property_style),
                        device_properties["id_"],
                        ("\nVendor: ", property_style),
                        device_properties["vendor"],
                        ("\nVersion: ", property_style),
                        device_properties["version"],
                        ("\nTL type: ", property_style),
                        device_properties["tl_type"],
                        ("\nUser defined name: ", property_style),
                        device_properties["user_defined_name"],
                        ("\nAccess Status: ", property_style),
                        f"{bool(device_properties['access_status'])}",
                    ),
                    title=f"Name: {device_properties['display_name']}",
                    border_style="royal_blue1",
                )
                devices_infos.append(device_infos)

        if self.verbose:
            console.print(Panel.fit(Group(*devices_infos), title="Devices Infos", border_style="chartreuse3"))

        return cameras

    def select_camera(self, camera_id_number) -> DeviceInfo:
        devices = self.check_cameras()
        device = devices.get(camera_id_number, None)
        console = Console()
        if device is None:
            other_possibilities = (
                f"Other cameras with ID: {', '.join(devices.keys())} are available"
                if len(devices)
                else "No camera appear to be accessible"
            )
            console.print(
                Text.assemble(
                    (
                        f"Unable to access the camera with ID: {camera_id_number}.\n{other_possibilities}.\n",
                        "bright_red",
                    ),
                    ("Check :\n", "deep_pink3"),
                    ("  - that your camera is powered up (fisrt)\n", "yellow1"),
                    ("  - your connections (second)\n", "yellow1"),
                    ("  - if other istances accessing the camera are still running (third)\n", "yellow1"),
                    ("  - and eventually your driver installation (last)", "yellow1"),
                    (
                        " Look at the output of get_genicam_driver_location for driver related issues informations",
                        "grey23",
                    ),
                )
            )
            sys.exit()
        return device

    def create(
        self, search_key: int | Dict[str, str] | DeviceInfo | None = None, *, config: ParameterSet | None = None
    ) -> ImageAcquirer:

        try:
            return super().create(search_key, config=config)
        except AccessDeniedException as e:
            if isinstance(search_key, DeviceInfo):
                device_name = search_key.property_dict["display_name"]
            elif isinstance(search_key, dict):
                device_name = search_key["display_name"]
            else:
                device_name = search_key

            console = Console()
            console.print(
                Text.assemble(
                    (f"{type(e).__name__}:", "bold bright_red"),
                    f" {e}\n",
                    ("Cannot get control access", "bright_red"),
                    " on device ",
                    (f'"{device_name}"', "bold blue"),
                    ". Maybe it is already opened by another service ? Ensure to close all systems using it, "
                    "and retry.",
                )
            )
            sys.exit()

    def acquire(self, camera_id_number: str):

        console = Console()
        device = self.select_camera(camera_id_number)

        with self.create(device) as acquirer:

            acquirer.start_acquisition()

            while True:
                buffer: Buffer = acquirer.fetch()  # type: ignore
                if buffer is None:
                    console.print("No data to acquire. Timeout")
                    continue

                if buffer.payload is None:
                    console.print("The payload of the buffer acquired was empty.")
                    continue

                image_data: Component2DImage = buffer.payload.components[0]  # type: ignore
                if image_data.data is None:
                    console.print("No image data was found in the buffer's payload.")
                    continue

                image = np.reshape(image_data.data, (image_data.height, image_data.width))
                console.print(f"Recieved an image of size : {image.shape}.")

    def show_available_nodes(self, camera_id_number: str, exclude_unaccessibles=True):
        console = Console()
        device = self.select_camera(camera_id_number)

        node_renderer = NodeRenderer(exclude_unaccessible_nodes=exclude_unaccessibles)

        with self.create(device) as acquirer:
            console.print(node_renderer.render(acquirer.device.node_map))
            console.print(node_renderer.render(acquirer.remote_device.node_map))


class NodeRenderer:
    """render python rich console text for genicam api nodes hierarchies.
    Colors and styles can be tuned with class attributes passed to init as regular kwargs arguments
    (key value pair arguments)"""

    title_style = "dark_slate_gray2"

    root_panel_style = "chartreuse3"
    category_panel_style = "royal_blue1"
    node_panel_style = "dark_slate_gray2"
    command_panel_style = "plum3"
    sub_property_style = "dark_slate_gray3"
    enum_entry_style = "dark_magenta"
    error_style = "bright_red"
    warning_style = "orange3"

    exclude_unaccessible_nodes = True

    def __init__(self, **kwargs):
        """Initializes the object with the provided key-value pairs.

        Args:
            **kwargs: Variable keyword arguments to set as attributes of the object.
        """

        for key, value in kwargs.items():
            setattr(self, key, value)

    # def render_root_node(self, node_map: NodeMap, title: str):
    #     """Render the root node with the given title.

    #     Args:
    #         node_map (NodeMap): The mapping of nodes.
    #         title (str): The title of the root node.

    #     Returns:
    #         Panel: The rendered panel of the root node.
    #     """
    #     # nodes[0] because we scan from root node into the whild nodes directly in the render_node function
    #     root_node = node_map.nodes[0]
    #     child_nodes_renders = self.render_node(root_node)
    #     if child_nodes_renders is None:
    #         raise ValueError

    #     panel = Panel.fit(
    #         child_nodes_renders,
    #         title=title,
    #         border_style=self.root_panel_style,
    #     )

    #     return panel

    # def render_title(self, title: str):
    #     """Renders the title with the specified text.

    #     Args:
    #         title (str): The text to be rendered as the title.

    #     Returns:
    #         Text: The rendered title text with the specified style.
    #     """
    #     return Text(f"\n{title}: ", style=self.title_style)

    def get_base_fields(self, item, include_value=True) -> Dict[str, Any]:
        """Return the base fields of an item.

        Args:
            item: The item to extract base fields from.
            include_value (bool): Whether to include the current value of the item. Default is True.

        Returns:
            dict: A dictionary containing the base fields of the item, including Description and Type.
                If include_value is True, Current Value is also included.
        """
        base_fields = {
            "Description": item.node.description,
            "Type": f"{type(item).__name__}"[1:],
        }
        if include_value:
            base_fields["Current Value"] = item.value
        return base_fields

    def get_increment_fields(self, item: IInteger | IFloat) -> Dict[str, str]:

        def capitalize(string: str):
            _string = []
            for location, char in enumerate(string):
                if location == 0:
                    char = char.upper()
                elif char.isupper():
                    _string.append(" ")
                _string.append(char)

            return "".join(_string)

        inc_mode = EIncMode(item.inc_mode)
        return (
            {
                "Increment Mode": f"{capitalize(inc_mode.name)} : (Mode n° {inc_mode.value})",
                "Increment Value": item.inc,
            }
            if inc_mode != EIncMode.noIncrement
            else {}
        )

    def get_notation_precision_fields(self, item: IFloat) -> Dict[str, str]:
        notation = EDisplayNotation(item.display_notation)
        return {
            "Display Precision": item.display_precision,
            "Display Notation": f"{notation.name} (Mode n°{notation.value})",
        }

    def get_minmax_fields(self, item: IInteger | IFloat) -> Dict[str, str]:
        return {"Maximum Value": item.max, "Minimum Value": item.min}

    def get_unit_field(self, item: IInteger | IFloat) -> Dict[str, str]:
        return {"Unit": item.unit} if item.unit else {}

    def get_representation_field(self, item: IInteger | IFloat) -> Dict[str, str]:
        representation = ERepresentation(item.representation)
        return {"Representation": f"{representation.name} (Mode n°{representation.value})"}

    def get_maximum_length_field(self, item: IString) -> Dict[str, Any]:
        return {"Maximum Length": item.max_length}

    # def render_node(self, item: IValue):
    #     """Render the given item based on its type and return the rendered output.

    #     Args:
    #         item (IValue): The item to be rendered.

    #     Returns:
    #         str: The rendered output of the item.

    #     Raises:
    #         NotImplementedError: If the item type is not supported for rendering.
    #     """

    #     try:
    #         if isinstance(item, ICategory):
    #             outputs = [self.render_node(subitem) for subitem in item.features]

    #             # We skip the category Panel if it's empty, due to unshown nodes
    #             # (tuneable with exclude_unaccessible_nodes attribute)
    #             outputs = [
    #                 out for out in outputs if out is not None or (isinstance(
    # out, (Panel, Padding)
    # ) and out.renderable)
    #             ]
    #             if not outputs:
    #                 return None

    #             # We return the Category Panel if it's not empty
    #             return Panel(Group(*outputs), title=item.node.display_name, border_style=self.category_panel_style)

    #         elif isinstance(item, IRegister):
    #             pass

    #         elif isinstance(item, IEnumeration):
    #             fields = self.get_base_fields(item)
    #             fields["Current Value"] = self.render_enum_entry(item.get_current_entry(), padding=0, prefix="")
    #             fields["Possible Values"] = ""
    #             additional_lines = [self.render_node(subitem) for subitem in item.entries]
    #             return self.render_fields(fields, item, additional_lines)

    #         elif isinstance(item, IInteger):
    #             fields = self.get_base_fields(item)
    #             fields.update(self.get_minmax_fields(item))
    #             fields.update(self.get_increment_fields(item))
    #             fields.update(self.get_representation_field(item))
    #             fields.update(self.get_unit_field(item))
    #             return self.render_fields(fields, item)

    #         elif isinstance(item, IFloat):
    #             fields = self.get_base_fields(item)
    #             fields.update(self.get_minmax_fields(item))
    #             fields.update(self.get_notation_precision_fields(item))
    #             fields.update(self.get_increment_fields(item))
    #             fields.update(self.get_representation_field(item))
    #             fields.update(self.get_unit_field(item))
    #             return self.render_fields(fields, item)

    #         elif isinstance(item, IString):
    #             fields = self.get_base_fields(item)
    #             fields.update(self.get_maximum_length_field(item))
    #             return self.render_fields(fields, item)

    #         elif isinstance(item, IBoolean):
    #             fields = self.get_base_fields(item)
    #             return self.render_fields(fields, item)

    #         elif isinstance(item, IEnumEntry):
    #             return self.render_enum_entry(item)

    #         elif isinstance(item, ICommand):
    #             fields = self.get_base_fields(item, include_value=False)
    #             fields["Execute"] = "run .execute() to execute this command."
    #             return self.render_fields(fields, item, item_style=self.command_panel_style)

    #         else:
    #             raise NotImplementedError(
    #                 "Unable to render the item, usupported type. Please add support to it to visualize all it's "
    #                 "properties correctly"
    #             )

    #     except AccessException as e:
    #         if self.exclude_unaccessible_nodes:
    #             return None
    #         fields = self.get_base_fields(item, include_value=False)
    #         fields.update({"Class Value": str(item), "Exception": type(e).__name__, "Error": str(e)})
    #         return self.render_fields(fields, item, item_style=self.warning_style)

    #     except Exception as e:
    #         fields = self.get_base_fields(item, include_value=False)
    #         fields.update({"Class Value": str(item), "Exception": type(e).__name__, "Error": str(e)})
    #         return self.render_fields(fields, item, item_style=self.error_style)

    def render_not_implemented_node(self, item: IValue):
        fields = self.get_base_fields(item, include_value=False)
        fields.update(
            {
                "Class Value": str(item),
                "Exception": "NotImplementedError",
                "Error": "Unable to render the item, usupported type. Please add support to it to visualize all it's "
                "properties correctly",
            }
        )
        return self.render_fields(fields, item, item_style=self.error_style)

    def render_inaccessible_node(self, item: IValue) -> Panel:
        fields = self.get_base_fields(item, include_value=False)
        fields.update(
            {
                "Class Value": str(item),
                "Exception": "NotImplementedError",
                "Error": "Unable to render the item, usupported type. Please add support to it to visualize all it's "
                "properties correctly",
            }
        )
        return self.render_fields(fields, item, item_style=self.warning_style)

    def render_error_node(self, item: IValue, exception: Exception) -> Panel | None:
        fields = self.get_base_fields(item, include_value=False)
        fields.update({"Class Value": str(item), "Exception": type(exception).__name__, "Error": str(exception)})
        return self.render_fields(fields, item, item_style=self.error_style)

    def render_category(self, item: ICategory) -> Panel | None:

        elements = [self.render(element) for element in item.features]

        # We skip the category Panel if it's empty, due to unshown nodes
        # (tuneable with exclude_unaccessible_nodes attribute)
        elements = [
            element
            for element in elements
            if element is not None or (isinstance(element, (Panel, Padding)) and element.renderable)
        ]
        if not elements:
            return None

        # We return the Category Panel if it's not empty
        return Panel(Group(*elements), title=item.node.display_name, border_style=self.category_panel_style)

    def render_register(self, item: IRegister):
        return None

    def render_enumeration(self, item: IEnumeration):
        fields = self.get_base_fields(item)
        fields["Current Value"] = self.render_enum_entry(item.get_current_entry(), padding=0, prefix="")
        fields["Possible Values"] = ""
        additional_lines = [self.render(subitem) for subitem in item.entries]
        return self.render_fields(fields, item, additional_lines)

    def render_float(self, item: IFloat):
        fields = self.get_base_fields(item)
        fields.update(self.get_minmax_fields(item))
        fields.update(self.get_notation_precision_fields(item))
        fields.update(self.get_increment_fields(item))
        fields.update(self.get_representation_field(item))
        fields.update(self.get_unit_field(item))
        return self.render_fields(fields, item)

    def render_integer(self, item: IInteger):
        fields = self.get_base_fields(item)
        fields.update(self.get_minmax_fields(item))
        fields.update(self.get_increment_fields(item))
        fields.update(self.get_representation_field(item))
        fields.update(self.get_unit_field(item))
        return self.render_fields(fields, item)

    def render_boolean(self, item: IBoolean):
        fields = self.get_base_fields(item)
        return self.render_fields(fields, item)

    def render_command(self, item: ICommand):
        fields = self.get_base_fields(item, include_value=False)
        fields["Execute"] = "run .execute() to execute this command."
        return self.render_fields(fields, item, item_style=self.command_panel_style)

    def render_string(self, item: IString):
        fields = self.get_base_fields(item)
        fields.update(self.get_maximum_length_field(item))
        return self.render_fields(fields, item)

    def render_enum_entry(self, item: IEnumEntry, padding=2, prefix="- "):
        """Render an enum entry with the specified padding and prefix.

        Args:
            item: The enum entry to render.
            padding (int): The padding to apply around the rendered entry. Defaults to 2.
            prefix (str): The prefix to prepend to the rendered entry. Defaults to "- ".

        Returns:
            Padding: The rendered enum entry with the specified styling.
        """
        return Padding(
            Text.assemble((f"{prefix}{item.node.display_name}: ", self.enum_entry_style), f"{item.value}"),
            (0, 0, 0, padding),
        )

    def get_node_renderer(self, node: IValue) -> Callable[[IValue], Panel | None]:

        def _node_skipper(_node) -> None:
            return None

        factories = {
            ICategory: self.render_category,
            IRegister: self.render_register,
            IEnumeration: self.render_enumeration,
            IString: self.render_string,
            IFloat: self.render_float,
            IInteger: self.render_integer,
            IBoolean: self.render_boolean,
            IEnumEntry: self.render_enum_entry,
            ICommand: self.render_command,
        }

        for node_type, function in factories.items():
            node_access = node.get_access_mode()
            if node_access < EAccessMode.WO or node_access > EAccessMode._UndefinedAccesMode:
                if self.exclude_unaccessible_nodes:
                    return _node_skipper
                else:
                    return self.render_inaccessible_node

            if isinstance(node, node_type):
                return function

        return self.render_not_implemented_node

    def render_property(self, key: str, value: Any, prefix="- "):
        """Render a sub property with the specified key and value.

        Args:
            key (str): The key of the sub property.
            value (Any): The value of the sub property.
            prefix (str, optional): The prefix to be added before the key. Defaults to "- ".

        Returns:
            Text: The rendered sub property text.
        """
        text = Text()
        text.append(f"{prefix}{key}: ", style=self.sub_property_style)
        if isinstance(value, Text):
            text.append(value)
        if isinstance(value, Padding):
            text.append(value.renderable)  # type: ignore
        else:
            text.append(f"{value}", style="grey23")
        return text

    def render_fields(self, fields, item: IValue, additional_lines=None, item_style=None):
        """Renders an item with specified fields and additional lines.

        Args:
            fields (dict): A dictionary containing keys and values to render.
            item (IValue): The item to render.
            additional_lines (list, optional): Additional lines to include in the rendering. Defaults to None.
            item_style (str, optional): The style of the item. Defaults to None.

        Returns:
            Panel: A Panel object containing the rendered item.
        """

        # if usit property is None, False or empty, we don't render it.
        lines = [self.render_property(key, value) for key, value in fields.items() if not (key == "Unit" and not value)]
        if additional_lines is not None:
            lines.extend(additional_lines)

        return Panel.fit(
            Padding(Group(*lines), (0, 0, 0, 2)),
            title=f"{item.node.display_name}",
            title_align="left",
            border_style=self.node_panel_style if item_style is None else item_style,
            width=150,
        )

    def render(self, node: IValue | NodeMap, title: Optional[str] = None) -> Panel | None:

        if isinstance(node, NodeMap):
            nodemap = node
            model_name = nodemap.device_info.model_name
            if title is None:
                title = f"Nodes informations for the device: {model_name}"
            renders = self.render(nodemap.nodes[0])
            if renders is None:
                raise ValueError(f"Unable to show any node from the nodemap for {title}")
            panel = Panel.fit(
                renders,
                title=title,
                border_style=self.root_panel_style,
            )

        else:
            try:
                renderer = self.get_node_renderer(node)
                panel = renderer(node)
            except Exception as e:
                panel = self.render_error_node(node, e)

        return panel
