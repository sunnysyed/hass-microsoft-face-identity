
import asyncio
import logging
import requests
import json
import time
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.helpers.entity import Entity
from homeassistant.components.image_processing import DOMAIN, CONF_CONFIDENCE, ImageProcessingFaceEntity
from homeassistant.const import CONF_NAME, CONF_API_KEY, CONF_URL, CONF_TIMEOUT, ATTR_NAME, ATTR_ENTITY_ID, HTTP_BAD_REQUEST, HTTP_OK, HTTP_UNAUTHORIZED, CONF_SOURCE, CONF_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

MICROSOFT_FACE_IDENTITY = 'microsoft_face_identity'

FACE_API_URL = "api.cognitive.microsoft.com/face/v1.0/{0}"

URL_VISION = "{0}/vision/v2.0/{1}"
SERVICE_DETECT = 'detect'
SERVICE_IDENTIFY = 'identify'
SERVICE_SNAPSHOT = 'snapshot'

CONF_AZURE_REGION  = "azure_region"
CONF_GROUP = "group"
CONF_RECOGNITION_MODEL  = "recognition_model"
CONF_DETECTION_MODEL  = "detection_model"


ATTR_CAMERA_ENTITY = 'camera_entity'
ATTR_DESCRIPTION = 'description'
ATTR_JSON = 'json'
ATTR_CONFIDENCE = 'confidence'
ATTR_BRAND = 'brand'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_GROUP): cv.string,
        vol.Optional(CONF_AZURE_REGION, default="useast2"): cv.string,
        vol.Optional(CONF_CONFIDENCE, default=80): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=100)
        ),
        vol.Optional(CONF_RECOGNITION_MODEL, default="recognition_01"): cv.string,
        vol.Optional(CONF_DETECTION_MODEL, default="detection_01"): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

SCHEMA_CALL_SERVICE = vol.Schema({
    vol.Required(ATTR_CAMERA_ENTITY): cv.string,
})

async def async_setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the platform."""
    if MICROSOFT_FACE_IDENTITY not in hass.data:
        hass.data[MICROSOFT_FACE_IDENTITY] = None
    try:
        devices = []
        for camera in config[CONF_SOURCE]:            
            device = MicrosoftFaceIdentifyDevice (
                hass,
                camera[CONF_ENTITY_ID],
                config.get(CONF_AZURE_REGION), 
                config.get(CONF_API_KEY),
                config.get(CONF_GROUP),
                config.get(CONF_CONFIDENCE),
                config.get(CONF_RECOGNITION_MODEL),
                config.get(CONF_DETECTION_MODEL)
                camera.get(CONF_NAME),
            )
            devices.append(device)
            hass.data[MICROSOFT_FACE_IDENTITY] = device
        add_devices(devices)
    except HomeAssistantError as err:
        _LOGGER.error("Error calling setup: %s", err)

    async def detect(service):
        device = hass.data[MICROSOFT_FACE_IDENTITY]
        try:
            await device.call_api(SERVICE_DETECT)
        except HomeAssistantError as err:
            _LOGGER.error("Error calling analyze: %s", err)

    hass.services.async_register(DOMAIN, SERVICE_DETECT, detect)

    async def identify(service):
        device = hass.data[MICROSOFT_FACE_IDENTITY]
        try:
            await device.call_api(SERVICE_IDENTIFY)
        except HomeAssistantError as err:
            _LOGGER.error("Error calling describe: %s", err)

    hass.services.async_register(DOMAIN, SERVICE_IDENTIFY, identify)

    async def snapshot(service):
        camera_entity = service.data.get(ATTR_CAMERA_ENTITY)
        camera = hass.components.camera
        device = hass.data[MICROSOFT_FACE_IDENTITY]
        image = None
        try:
            image = await camera.async_get_image(camera_entity)
            device.set_image(image)
        except HomeAssistantError as err:
            _LOGGER.error("Error on receive image from entity: %s", err)

    hass.services.async_register(DOMAIN, SERVICE_SNAPSHOT, snapshot, schema=SCHEMA_CALL_SERVICE)
  
    return True

class MicrosoftFaceIdentifyDevice(ImageProcessingFaceEntity):
    """Representation of a platform."""

    def __init__(self, hass, camera_entity, region, api_key, group, confidence, recognition_model, detection_model, name=MICROSOFT_FACE_IDENTITY):
        """Initialize the platform."""
        self._hass = hass
        self._camera = camera_entity
        self._name = name
        self._api_key = api_key
        self._region = region
        self._description = None
        self._brand = None
        self._json = None
        self._image = None
        self._confidence = confidence
        self._group = group
        self._recognition_model = recognition_model
        self._detection_model = detection_model

    @property
    def name(self):
        """Return the name of the platform."""
        return self._name

    @property
    def description(self):
        """Return the description of the platform."""
        return self._description

    @property
    def brand(self):
        """Return the brand of the platform."""
        return self._brand

    @property
    def json(self):
        """Return the JSON of the platform."""
        return self._json

    @property
    def confidence(self):
        """Return the confidence of the platform."""
        return self._confidence
    
    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    async def call_api(self, service):
        await self._hass.async_add_executor_job(self.post_api, service)

    def post_api(self, service):
        # try:
        #     headers = {"Ocp-Apim-Subscription-Key": self._api_key,
        #                "Content-Type": "application/octet-stream"}
        #     params = None
        #     url = URL_VISION.format(self._endpoint, service)
        #     if service == SERVICE_ANALYZE:
        #         params =  {"visualFeatures": self._visual_features}
        #     if service == SERVICE_RECOGNIZE_TEXT:
        #         params =  {"mode": self._text_mode}
        #         url = URL_VISION.format(self._endpoint, "recognizeText")

        #     self._json = None
        #     self._description = None
        #     self._brand = None
        #     self._confidence = None
        #     self._state = None
        #     self.async_schedule_update_ha_state()

        #     response = requests.post(url, headers=headers, params=params, data=self._image.content)
        #     response.raise_for_status()
            
        #     if response.status_code == 200:
        #         self._state = "ready"
        #         self._json = response.json()
        #         if "description" in self._json:
        #             self._description = self._json["description"]["captions"][0]["text"]
        #             self._confidence = round(100 * self._json["description"]["captions"][0]["confidence"])
        #         if "brands" in self._json and len(self._json["brands"]) != 0:
        #             self._brand = self._json["brands"][0]["name"]

        #     if response.status_code == 202:
        #         _LOGGER.info(response.headers)
        #         url = response.headers["Operation-Location"]
        #         time.sleep(5)
        #         response = requests.get(url, headers=headers)
        #         response.raise_for_status()
        #         self._json = response.json()

        #         if self._json["status"] == "Succeeded":
        #             self._state = "ready"
        #             for line in self._json["recognitionResult"]["lines"]:
        #                 for word in line["words"]:
        #                     if "confidence" not in word:
        #                         self._description = word["text"] if self.description is None else self.description + " " + word["text"]

        #     self.async_schedule_update_ha_state()

        # except:
        #     raise
        _LOGGER.info("MAKE API CALL")
    
    async def async_process_image(self, image):
        """Process image.
        This method is a coroutine.
        """
        detect = []
        try:
            face_data = await self.call_api("post", "detect", image, binary=True)

            if face_data:
                face_ids = [data["faceId"] for data in face_data]
                detect = await self.call_api(
                    "post",
                    "identify",
                    {"faceIds": face_ids, "personGroupId": self._group},
                )

        except HomeAssistantError as err:
            _LOGGER.error("Can't process image on Microsoft face: %s", err)
            return

        # Parse data
        known_faces = []
        total = 0
        for face in detect:
            total += 1
            if not face["candidates"]:
                continue

            data = face["candidates"][0]
            name = ""
            # for s_name, s_id in self.store[self._group].items():
            #     if data["personId"] == s_id:
            #         name = s_name
            #         break

            known_faces.append(
                {ATTR_NAME: name, ATTR_CONFIDENCE: data["confidence"] * 100}
            )

        self.async_process_faces(known_faces, total)