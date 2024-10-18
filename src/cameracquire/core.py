from pathlib import Path
import numpy as np

from harvesters.core import Harvester, DeviceInfo, ImageAcquirer, Buffer, Component2DImage, ParameterSet

from genicam.gentl import AccessDeniedException

from typing import Sequence, List, Dict, Any, Callable, Optional
from types import ModuleType
import sys

from .render_backends import get_default_backends, get_backend

# download latest GenTL producer .exe from http://static.matrix-vision.com/mvIMPACT_Acquire/
# install, and find it in C:\Program Files\Balluff\ImpactAcquire\bin\x64

IMPACT_ACQUIRE_LOCATIONS = ["C:/Program Files/Balluff", "C:/Program Files/MATRIX VISION"]
IMPACT_PATH_TO_CTI = "ImpactAcquire/bin/x64/mvGenTLProducer.cti"

class CameraDriver(Harvester):

    cti_search_locations = [Path(install_location) / IMPACT_PATH_TO_CTI for 
                            install_location in IMPACT_ACQUIRE_LOCATIONS]

    def __init__(self, *args, verbose=True, render_backends = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.verbose = verbose
        self.render_backend = render_backend if render_backend is not None else 

    def __enter__(self):
        self = super().__enter__()
        self.get_genicam_driver_location()  # finds the proper genicam driver.
        # Needs to be installed, if not installed will provide a usefull message
        self.update()  # update devices infos
        return self

    def get_genicam_driver_location(self) -> None:

        for cti_file in self.cti_search_locations:
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
            "This package will then try to look for .cti files at "
            f"either of these locations : {', '.join([str(file) for file in self.cti_search_locations])}. "
            " Please make sure it exists into one of these locations if the error persists."
        )

    def check_cameras(self) -> Dict[str, DeviceInfo]:

        device_info_list = self.device_info_list if self.device_info_list else []
        cameras = {device.property_dict["id_"] : device for device in device_info_list}
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

        device = self.select_camera(camera_id_number)
        with self.create(device) as acquirer:
            NodeRenderer(exclude_unaccessible_nodes=exclude_unaccessibles).print_camera_nodes(acquirer)

    def show_node(self,camera_id_number)


class Camera:

    def __init__(self, driver : CameraDriver, camera_id):

        self.driver = driver

    


