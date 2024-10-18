from pathlib import Path
import numpy as np

from harvesters.core import Harvester, DeviceInfo, ImageAcquirer, Buffer, Component, Component2DImage, ParameterSet

from genicam.gentl import AccessDeniedException

from typing import Sequence, List, Dict, Any, Callable, Optional
import sys

from .render_backends import get_backends

# download latest GenTL producer .exe from http://static.matrix-vision.com/mvIMPACT_Acquire/
# install, and find it in C:\Program Files\Balluff\ImpactAcquire\bin\x64

IMPACT_ACQUIRE_LOCATIONS = [
    "C:/Program Files/Balluff", "C:/Program Files/MATRIX VISION"]
IMPACT_PATH_TO_CTI = "ImpactAcquire/bin/x64/mvGenTLProducer.cti"


class CameraDriver(Harvester):

    cti_search_locations = [Path(install_location) / IMPACT_PATH_TO_CTI for
                            install_location in IMPACT_ACQUIRE_LOCATIONS]

    def __init__(self, *args, verbose=True, render_backends: Optional[List[str]] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.verbose = verbose
        self.render_backends = get_backends(render_backends)

    def __enter__(self):
        self = super().__enter__()
        self.get_genicam_driver_location()  # finds the proper genicam driver.
        # Needs to be installed, if not installed will provide a usefull message
        self.update()  # update devices infos
        return self

    def get_genicam_driver_location(self) -> None:

        for cti_file in self.cti_search_locations:
            if cti_file.exists:
                self.add_file(str(cti_file),
                              check_existence=True,
                              check_validity=True)

        self.render_backends.render("DriverCTIRenderer", self)

        if not len(self._cti_files):
            # if no file is found, we stop the code here
            sys.exit()

    def check_cameras(self) -> Dict[str, DeviceInfo]:

        device_info_list = self.device_info_list if self.device_info_list else []
        cameras = {device.property_dict["id_"]: device for device in device_info_list}
        self.render_backends.render("DeviceInfoRenderer", cameras)
        return cameras

    def select_camera(self, camera_id_number) -> DeviceInfo:
        devices = self.check_cameras()
        device = devices.get(camera_id_number, None)
        self.render_backends.render(
            "DeviceSelectionRenderer", devices, device, camera_id_number)
        if device is None:
            sys.exit()
        return device

    def create(
        self, search_key: int | Dict[str, str] | DeviceInfo | None = None, *, config: ParameterSet | None = None
    ) -> ImageAcquirer:

        try:
            return super().create(search_key, config=config)
        except AccessDeniedException as exception:
            self.render_backends.render(
                "DeviceDeniedAccessRenderer", exception, search_key)
            sys.exit()

    def acquire(self, camera_id_number: str):

        device = self.select_camera(camera_id_number)

        with self.create(device) as acquirer:

            acquirer.start_acquisition()

            while True:
                buffer: Buffer = acquirer.fetch()  # type: ignore
                if buffer is None:
                    self.render_backends.render("NoDataRenderer")
                    continue

                if buffer.payload is None:
                    self.render_backends.render("PayloadEmptyRenderer")
                    continue

                # type: ignore
                # Component2DImage
                image_data: Component = buffer.payload.components[0]
                if image_data.data is None:
                    self.render_backends.render(
                        "PayloadComponentEmptyRenderer")
                    continue

                image = np.reshape(
                    image_data.data, (image_data.height, image_data.width))
                console.print()

    def show_available_nodes(self, camera_id_number: str, exclude_unaccessibles=True):

        device = self.select_camera(camera_id_number)
        with self.create(device) as acquirer:
            self.render_backends.render("NodeRenderer", acquirer)


# class Camera:

#     def __init__(self, driver: CameraDriver, camera_id):

#         self.driver = driver
