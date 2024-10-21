from pathlib import Path
import numpy as np

from harvesters.core import Harvester, DeviceInfo, ImageAcquirer, Buffer, Component2DImage, ParameterSet
from genicam.gentl import AccessDeniedException, TimeoutException
from genicam.genapi import ICommand, IEnumeration

from typing import List, Dict, Optional
import sys

from .render_backends import get_backends

# download latest GenTL producer .exe from http://static.matrix-vision.com/mvIMPACT_Acquire/
# install, and find it in C:\Program Files\Balluff\ImpactAcquire\bin\x64

IMPACT_ACQUIRE_LOCATIONS = ["C:/Program Files/Balluff", "C:/Program Files/MATRIX VISION"]
IMPACT_PATH_TO_CTI = "ImpactAcquire/bin/x64/mvGenTLProducer.cti"


class CameraDriver(Harvester):

    cti_search_locations = [
        Path(install_location) / IMPACT_PATH_TO_CTI for install_location in IMPACT_ACQUIRE_LOCATIONS
    ]

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
            if cti_file.is_file():
                self.add_file(str(cti_file), check_existence=True, check_validity=True)

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
        self.render_backends.render("DeviceSelectionRenderer", devices, device, camera_id_number)
        if device is None:
            sys.exit()
        return device

    def create(
        self, search_key: int | Dict[str, str] | DeviceInfo | None = None, *, config: ParameterSet | None = None
    ) -> ImageAcquirer:

        try:
            return super().create(search_key, config=config)
        except AccessDeniedException as exception:
            self.render_backends.render("DeviceDeniedAccessRenderer", exception, search_key)
            sys.exit()

    def execute_command(self, acquirer: ImageAcquirer, command=""):

        starter: ICommand = acquirer.remote_device.node_map.get_node(command)
        starter.execute()

    def select_user_set(self, acquirer: ImageAcquirer, user_set=0):

        selector: IEnumeration = acquirer.remote_device.node_map.get_node("UserSetSelector")
        loader: ICommand = acquirer.remote_device.node_map.get_node("UserSetLoad")
        selector.set_int_value(user_set)
        loader.execute()

    def set_free_run(self, acquirer: ImageAcquirer):

        free_runner: IEnumeration = acquirer.remote_device.node_map.get_node("TriggerMode")
        free_runner.set_value("Off")

    def acquire(self, camera_id_number: str):

        device = self.select_camera(camera_id_number)

        with self.create(device) as acquirer:

            self.select_user_set(acquirer, 0)
            self.set_free_run(acquirer)
            acquirer.start(run_as_thread=False)

            while True:
                try:
                    buffer: Buffer | None = acquirer.fetch(timeout=2, cycle_s=0.1)  # type: ignore
                except TimeoutException:
                    buffer = None
                if buffer is None:
                    self.render_backends.render("NoDataRenderer")
                    continue

                if buffer.payload is None:
                    self.render_backends.render("PayloadEmptyRenderer")
                    continue

                image_data: Component2DImage = buffer.payload.components[0]  # type: ignore
                if image_data.data is None:
                    self.render_backends.render("PayloadComponentEmptyRenderer")
                    continue

                image = np.reshape(image_data.data, (image_data.height, image_data.width))
                self.render_backends.render("ImageRecievedNotificationRenderer", image.shape)
                self.render_backends.render("StreamImage", image)

    def show_available_nodes(self, camera_id_number: str, exclude_unaccessibles=True):

        device = self.select_camera(camera_id_number)
        with self.create(device) as acquirer:
            self.render_backends.render("NodeRenderer", acquirer)


# class Camera:

#     def __init__(self, driver: CameraDriver, camera_id):

#         self.driver = driver
