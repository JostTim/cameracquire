from genicam.genapi import (
    ICategory,
    ICommand,
    IInteger,
    IEnumeration,
    IString,
    IBoolean,
    IFloat,
    IValue,
    IRegister,
    IEnumEntry,
    EIncMode,
    ERepresentation,
    EDisplayNotation,
    EAccessMode,
    IntEnum,
    # IDeviceInfo,
    # AccessException,
)
from harvesters.core import ImageAcquirer, NodeMap, DeviceInfo, Payload

from rich.panel import Panel
from rich.text import Text
from rich.console import Group, Console
from rich.padding import Padding
from rich.traceback import install as install_rich_tracebacks
from rich.live import Live

from pathlib import Path
from typing import Sequence, List, Dict, Any, Callable, Optional, TYPE_CHECKING

from . import BaseRenderer, CrossInstanceCameraAttributes, CrossInstanceReferencer
from enum import Enum

if TYPE_CHECKING:
    from ..core import CameraDriver

# install_rich_tracebacks(show_locals=True)


class LogggingLevels(Enum):

    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3


LOGGING_LEVEL = LogggingLevels.INFO.value


class Renderer(BaseRenderer):

    def __init__(self, **kwargs):
        """Initializes the object with the provided key-value pairs.

        Args:
            **kwargs: Variable keyword arguments to set as attributes of the object.
        """

        for key, value in kwargs.items():
            setattr(self, key, value)

        self.console = Console()


class DriverCTIRenderer(Renderer):

    file_style = "reverse grey23"
    success_style = "bright_green"
    low_level_info_style = "grey23"
    error_style = "bright_red"

    def render(self, driver: "CameraDriver"):
        if not len(driver._cti_files):
            render = self.render_failure_message(driver)
        else:
            render = self.render_cti_files(driver._cti_files)
        self.console.print(render)

    def render_failure_message(self, driver: "CameraDriver"):
        return Text.assemble(
            (
                "Didn't found an installation of ImpactAcquire. Please download and install one. "
                "You can find it at this link : http://static.matrix-vision.com/mvIMPACT_Acquire/ "
                "Prefer using the lastest version. Once you clicked on it, select an executeable for your "
                "operating system (most likely ImpactAcquire-x86_64-X.X.X.exe "
                "if you are on a 64bit Windows computer).",
                self.error_style,
            ),
            (
                "This package will then try to look for .cti files at "
                f"either of these locations : {', '.join([str(file) for file in driver.cti_search_locations])}. "
                " Please make sure it exists into one of these locations if the error persists.",
                self.low_level_info_style,
            ),
        )

    def render_success_message(self):
        return Text("💽 ImpactAcquire driver loading success", style=self.success_style)

    def render_cti_file(self, cti_file: str | Path):
        return Text.assemble(
            ("Found a .cti file at ", self.low_level_info_style),
            (f"{cti_file}", self.file_style),
        )

    def render_cti_files(self, cti_files: List[str | Path]):

        infos = []
        infos.append(self.render_success_message())
        for cti_file in cti_files:
            infos.append(self.render_cti_file(cti_file))
        return Group(*infos)


class DeviceSelectionRenderer(Renderer):

    def render(self, cameras: Dict[str, DeviceInfo], selected_camera: DeviceInfo | None, selection_id: str | int):
        if selected_camera is None:
            render = self.render_not_found_message(cameras, selection_id)
        else:
            render = self.render_selected(selected_camera)
        self.console.print(render)

    def render_selected(self, selected_camera: DeviceInfo):
        return Text(f"Selected camera {selected_camera.property_dict['id_']}")

    def render_not_found_message(self, cameras: Dict[str, DeviceInfo], selection_id: str | int):
        other_possibilities = (
            f"Other cameras with ID: {', '.join(cameras.keys())} are available"
            if len(cameras)
            else "No camera appear to be accessible"
        )

        return Text.assemble(
            (
                f"Unable to access the camera with ID: {selection_id}.\n{other_possibilities}.\n",
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


class DeviceInfoRenderer(Renderer):

    property_style = "dark_slate_gray2"

    def render(self, cameras: Dict[str, DeviceInfo]):
        self.console.print(self.render_devices_infos(cameras))

    def get_no_device_message(self):
        return Text(
            "No device or camera is available. Check that you properly connected " "them and that they are powered on",
            style="bright_red",
        )

    def render_devices_infos(self, cameras: Dict[str, DeviceInfo]):
        if not len(cameras):
            return self.get_no_device_message()

        devices_infos = []
        for camera in cameras.values():
            device_properties = camera.property_dict
            devices_infos.append(self.render_device_infos(device_properties))
        return Panel.fit(Group(*devices_infos), title="Devices Infos", border_style="chartreuse3")

    def render_device_infos(self, device_properties: Dict[str, Any]):

        return Panel(
            Text.assemble(
                ("Model: ", self.property_style),
                device_properties["model"],
                ("\nSerial number: ", self.property_style),
                device_properties["serial_number"],
                ("\nID: ", self.property_style),
                device_properties["id_"],
                ("\nVendor: ", self.property_style),
                device_properties["vendor"],
                ("\nVersion: ", self.property_style),
                device_properties["version"],
                ("\nTL type: ", self.property_style),
                device_properties["tl_type"],
                ("\nUser defined name: ", self.property_style),
                device_properties["user_defined_name"],
                ("\nAccess Status: ", self.property_style),
                f"{bool(device_properties['access_status'])}",
            ),
            title=f"Name: {device_properties['display_name']}",
            border_style="royal_blue1",
        )


class DeviceDeniedAccessRenderer(Renderer):

    def render(self, exception: Exception, search_key: DeviceInfo | Dict[str, str] | str):

        if isinstance(search_key, DeviceInfo):
            device_name = search_key.property_dict["display_name"]
        elif isinstance(search_key, dict):
            device_name = search_key["display_name"]
        else:
            device_name = search_key

        render = Text.assemble(
            (f"{type(exception).__name__}:", "bold bright_red"),
            f" {exception}\n",
            ("Cannot get control access", "bright_red"),
            " on device ",
            (f'"{device_name}"', "bold blue"),
            ". Maybe it is already opened by another service ? Ensure to close all systems using it, " "and retry.",
        )

        self.console.print(render)


class SingleMessageRenderer(Renderer):

    message = ""
    style = None

    def render(self):
        self.console.print(self.message, style=self.style)


class NoDataRenderer(SingleMessageRenderer):
    message = "No data to acquire. Timeout"
    style = "bright_red"

    def render(self, exception: Optional[Exception] = None):
        self.console.print(f"{self.message}. {exception if exception is not None else ''}", style=self.style)


class PayloadEmptyRenderer(SingleMessageRenderer):
    message = "The payload of the buffer acquired was empty."
    style = "bright_red"


class PayloadComponentEmptyRenderer(SingleMessageRenderer):
    message = "No image data was found in the buffer's payload first component"
    style = "bright_red"


class AcquisitionStoppedRenderer(SingleMessageRenderer):
    message = "The acquisition stopped"
    style = "bright_orange"


class PayloadComponentsRenderer(Renderer):
    style = "blue"

    def render(self, payload: Payload):
        if LOGGING_LEVEL <= LogggingLevels.DEBUG.value:
            self.console.print(f"Payload type : {type(payload)}", style=self.style)

            components_types = [str(type(component)) for component in payload.components]
            self.console.print(f"Payload components : {components_types}", style=self.style)


class ImageRecievedNotificationRenderer(Renderer):

    MEMORY = CrossInstanceCameraAttributes()
    LIVE: CrossInstanceReferencer[Live] = CrossInstanceReferencer()

    def render(self, image_shape):
        self.MEMORY.update(image_shape)

        self.live.update(
            f"Total frames received: {self.MEMORY.total_frames} ({self.MEMORY.real_fps}fps) "
            f"at resolution: {self.MEMORY.image_shape}"
        )

    @property
    def live(self) -> Live:
        live = self.LIVE.get()
        if live is None:
            live = self.LIVE.set(Live(console=self.console, refresh_per_second=4).__enter__())
        return live


class NodeRenderer(Renderer):
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
    no_access_style = "grey69"

    exclude_unaccessible_nodes = True

    def render(self, item: IValue | NodeMap | ImageAcquirer, title: Optional[str] = None) -> Panel | None:

        if isinstance(item, ImageAcquirer):
            render = Group(*[self.render_nodemap(device.node_map) for device in (item.device, item.remote_device)])
        elif isinstance(item, NodeMap):
            render = self.render_nodemap(item, title)
        elif isinstance(item, IValue):
            render = self.render_node(item)
        else:
            raise NotImplementedError(f"Unsupported type: {type(item)}")
        self.console.print(render)

    def render_nodemap(self, nodemap: NodeMap, title: Optional[str] = None) -> Panel:
        model_name = nodemap.device_info.model_name
        if title is None:
            title = f"Nodes informations for the device: {model_name}"
        renders = self.render_node(nodemap.nodes[0])
        if renders is None:
            raise ValueError(f"Unable to show any node from the nodemap for {title}")
        panel = Panel.fit(
            renders,
            title=title,
            border_style=self.root_panel_style,
        )
        return panel

    def render_node(self, node: IValue) -> Panel | None:
        try:
            renderer = self.get_node_renderer(node)
            panel = renderer(node)
        except Exception as e:
            panel = self.render_error_node(node, e)
        return panel

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

    def uncamelcase(self, string):
        _string = []
        for location, char in enumerate(string):
            if location == 0:
                char = char.upper()
            elif char.isupper():
                _string.append(" ")
            _string.append(char)

        return "".join(_string)

    def get_increment_fields(self, item: IInteger | IFloat) -> Dict[str, str]:

        inc_mode = EIncMode(item.inc_mode)

        return (
            {
                "Increment Mode": self.get_enum_text(inc_mode),
                "Increment Value": item.inc,
            }
            if inc_mode != EIncMode.noIncrement
            else {}
        )

    def get_notation_precision_fields(self, item: IFloat) -> Dict[str, str]:
        return {
            "Display Precision": item.display_precision,
            "Display Notation": self.get_enum_text(EDisplayNotation(item.display_notation)),
        }

    def get_minmax_fields(self, item: IInteger | IFloat) -> Dict[str, str]:
        return {"Maximum Value": item.max, "Minimum Value": item.min}

    def get_unit_field(self, item: IInteger | IFloat) -> Dict[str, str]:
        return {"Unit": item.unit} if item.unit else {}

    def get_enum_text(self, enum_value: IntEnum):
        return f"{self.uncamelcase(enum_value.name)} (Mode n°{enum_value.value})"

    def get_representation_field(self, item: IInteger | IFloat) -> Dict[str, str]:
        return {"Representation": self.get_enum_text(ERepresentation(item.representation))}

    def get_maximum_length_field(self, item: IString) -> Dict[str, Any]:
        return {"Maximum Length": item.max_length}

    def get_ivalue_class(self, item: IValue):
        return {"Class Value": str(item)}

    def get_exception_error(self, exception: Exception | str, error=""):
        if isinstance(exception, Exception):
            exception = type(exception).__name__
            error += str(exception)
        return {"Exception": exception, "Error": error}

    def render_not_implemented_node(self, item: IValue) -> Panel:
        fields = self.get_base_fields(item, include_value=False)
        fields.update(self.get_ivalue_class(item))
        fields.update(
            self.get_exception_error(
                exception="NotImplementedError",
                error="Unable to render the item, usupported type. "
                "Please add support to it to visualize all it's properties correctly",
            )
        )
        return self.render_fields(fields, item, item_style=self.warning_style)

    def render_inaccessible_node(self, item: IValue) -> Panel:
        fields = self.get_base_fields(item, include_value=False)
        fields.update(self.get_ivalue_class(item))
        fields["Access"] = self.get_enum_text(EAccessMode(item.get_access_mode()))
        fields.update(
            self.get_exception_error(
                exception="AccessException",
                error="Unable to access the item entirely. It might be in protected access mode.",
            )
        )
        return self.render_fields(fields, item, item_style=self.no_access_style)

    def render_error_node(self, item: IValue, exception: Exception) -> Panel:
        fields = self.get_base_fields(item, include_value=False)
        fields.update(self.get_ivalue_class(item))
        fields.update(self.get_exception_error(exception=exception))
        return self.render_fields(fields, item, item_style=self.error_style)

    def render_category(self, item: ICategory) -> Panel | None:

        elements = [self.render_node(element) for element in item.features]

        # We skip the category Panel if it's empty, due to unshown nodes
        # (tuneable with exclude_unaccessible_nodes attribute)
        elements = [
            element
            for element in elements
            if element is not None or (isinstance(element, (Panel, Padding)) and element.renderable)
        ]
        # If the pannel would be empty, we don't return it, but None
        return (
            None
            if not elements
            else Panel(Group(*elements), title=item.node.display_name, border_style=self.category_panel_style)
        )

    def render_register(self, item: IRegister) -> Panel:
        fields = self.get_base_fields(item)
        fields["Address"] = item.address
        return self.render_fields(fields, item)

    def render_enumeration(self, item: IEnumeration) -> Panel:
        fields = self.get_base_fields(item)
        fields["Current Value"] = self.render_enum_entry(item.get_current_entry(), padding=0, prefix="")
        fields["Possible Values"] = ""
        additional_lines = [self.render_enum_entry(subitem) for subitem in item.entries]
        return self.render_fields(fields, item, additional_lines)

    def render_float(self, item: IFloat) -> Panel:
        fields = self.get_base_fields(item)
        fields.update(self.get_minmax_fields(item))
        fields.update(self.get_notation_precision_fields(item))
        fields.update(self.get_increment_fields(item))
        fields.update(self.get_representation_field(item))
        fields.update(self.get_unit_field(item))
        return self.render_fields(fields, item)

    def render_integer(self, item: IInteger) -> Panel:
        fields = self.get_base_fields(item)
        fields.update(self.get_minmax_fields(item))
        fields.update(self.get_increment_fields(item))
        fields.update(self.get_representation_field(item))
        fields.update(self.get_unit_field(item))
        return self.render_fields(fields, item)

    def render_boolean(self, item: IBoolean) -> Panel:
        fields = self.get_base_fields(item)
        return self.render_fields(fields, item)

    def render_command(self, item: ICommand) -> Panel:
        fields = self.get_base_fields(item, include_value=False)
        fields["Execute"] = "run .execute() to execute this command."
        return self.render_fields(fields, item, item_style=self.command_panel_style)

    def render_string(self, item: IString) -> Panel:
        fields = self.get_base_fields(item)
        fields.update(self.get_maximum_length_field(item))
        return self.render_fields(fields, item)

    def render_enum_entry(self, item: IEnumEntry, padding=2, prefix="- ") -> Padding:
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

        def skip_node(_node) -> None:
            return None

        factories = {
            ICategory: self.render_category,
            IRegister: self.render_register,
            IEnumeration: self.render_enumeration,
            IString: self.render_string,
            IFloat: self.render_float,
            IInteger: self.render_integer,
            IBoolean: self.render_boolean,
            IEnumEntry: skip_node,
            ICommand: self.render_command,
        }

        for node_type, function in factories.items():
            node_access = node.get_access_mode()
            if node_access < EAccessMode.WO or node_access > EAccessMode._UndefinedAccesMode:
                if self.exclude_unaccessible_nodes:
                    return skip_node
                else:
                    return self.render_inaccessible_node

            if isinstance(node, node_type):
                return function

        return self.render_not_implemented_node

    def render_property(self, key: str, value: Any, prefix="- ") -> Text:
        """Render a sub property with the specified key and value.

        Args:
            key (str): The key of the sub property.
            value (Any): The value of the sub property.
            prefix (str, optional): The prefix to be added before the key. Defaults to "- ".

        Returns:
            Text: The rendered sub property text.
        """
        text = Text(f"{prefix}{key}: ", style=self.sub_property_style)
        if isinstance(value, Text):
            text.append(value)
        if isinstance(value, Padding):
            text.append(value.renderable)  # type: ignore
        else:
            text.append(f"{value}", style="grey23")
        return text

    def render_fields(
        self,
        fields: Dict[str, str],
        item: IValue,
        additional_lines: Sequence[Text | Padding] = [],
        item_style=None,
    ) -> Panel:
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
        lines: List[Text | Padding] = [self.render_property(key, value) for key, value in fields.items()]
        lines += additional_lines

        return Panel.fit(
            Padding(Group(*lines), (0, 0, 0, 2)),
            title=f"{item.node.display_name}",
            title_align="left",
            border_style=self.node_panel_style if item_style is None else item_style,
            width=150,
        )
