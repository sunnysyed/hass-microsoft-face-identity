import json
from datetime import timedelta
import requests
import logging
import voluptuous as vol

from homeassistant.core import split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME, CONF_API_KEY, ATTR_NAME
from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA, ImageProcessingEntity, CONF_SOURCE, CONF_ENTITY_ID,
    CONF_NAME, CONF_CONFIDENCE, ImageProcessingFaceEntity, DOMAIN)
from homeassistant.exceptions import HomeAssistantError


_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)
FACE_API_URL = "api.cognitive.microsoft.com/face/v1.0"
CONF_AZURE_REGION  = "azure_region"
CONF_GROUP = "group"
CONF_RECOGNITION_MODEL  = "recognition_model"
CONF_DETECTION_MODEL  = "detection_model"

SERVICE_CREATE_GROUP = "create_group"
SERVICE_CREATE_PERSON = "create_person"
SERVICE_DELETE_GROUP = "delete_group"
SERVICE_DELETE_PERSON = "delete_person"
SERVICE_FACE_PERSON = "face_person"
SERVICE_TRAIN_GROUP = "train_group"

ATTR_CAMERA_ENTITY = "camera_entity"
ATTR_GROUP = "group"
ATTR_PERSON = "person"
ATTR_RECOGNITION_MODEL = "recognition_model"


ATTR_CONFIDENCE = 'confidence'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_GROUP): cv.string,
    vol.Optional(CONF_AZURE_REGION, default="useast2"): cv.string,
    vol.Optional(CONF_CONFIDENCE, default=80): vol.All(
        vol.Coerce(float), vol.Range(min=0, max=100)
    ),
    vol.Optional(CONF_RECOGNITION_MODEL, default="recognition_01"): cv.string,
    vol.Optional(CONF_DETECTION_MODEL, default="detection_01"): cv.string
})

SCHEMA_GROUP_SERVICE = vol.Schema({vol.Required(ATTR_NAME): cv.string})

SCHEMA_PERSON_SERVICE = SCHEMA_GROUP_SERVICE.extend(
    {vol.Required(ATTR_GROUP): cv.slugify}
)

SCHEMA_FACE_SERVICE = vol.Schema(
    {
        vol.Required(ATTR_PERSON): cv.string,
        vol.Required(ATTR_GROUP): cv.slugify,
        vol.Required(ATTR_CAMERA_ENTITY): cv.entity_id,
    }
)

SCHEMA_TRAIN_SERVICE = vol.Schema({vol.Required(ATTR_GROUP): cv.slugify})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the MicrosoftFaceApiIdentifyDevice."""
    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(MicrosoftFaceApiIdentifyDevice(
            hass,
            camera.get(CONF_NAME),
            camera[CONF_ENTITY_ID],
            config[CONF_API_KEY],
            config[CONF_GROUP],
            config[CONF_AZURE_REGION],
            config[CONF_CONFIDENCE],
            config[CONF_RECOGNITION_MODEL],
            config[CONF_DETECTION_MODEL],
        ))
    add_devices(entities)

    async def async_create_group(service):
        """Create a new person group."""
        name = service.data[ATTR_NAME]
        recognition_model = config[CONF_RECOGNITION_MODEL]
        try:
            url = f"https://{config[CONF_AZURE_REGION]}.{FACE_API_URL}/persongroups/{name}"
            payload = json.dumps({
                "name": name,
                "recognitionModel": recognition_model
            })
            headers = {
                'Content-Type': 'application/json',
                'Ocp-Apim-Subscription-Key': config[CONF_API_KEY]
            }
            response = requests.request("PUT", url, headers=headers, data=payload)
            print(response.text)
        except HomeAssistantError as err:
            _LOGGER.error("Can't create group '%s' with error: %s", name, err)

    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_GROUP, async_create_group, schema=SCHEMA_GROUP_SERVICE
    )

class MicrosoftFaceApiIdentifyDevice(ImageProcessingFaceEntity):
    """Perform a MicrosoftFaceApi call to detect and identify"""

    ICON = 'mdi:account-search'

    def __init__(self, hass, name, camera_entity, api_key, group, region, confidence, recognition_model, detection_model):
        self.hass = hass
        if name:  # Since name is optional.
            self._name = name
        else:
            self._name = "Microsoft Face API {0}".format(
                split_entity_id(camera_entity)[1])
        self._camera_entity = camera_entity
        self._api_key = api_key
        self._group = group
        self._region = region
        self._confidence = confidence
        self._recognition_model = recognition_model
        self._detection_model = detection_model
        self.faces = []
        self.total_faces = 0
        self._store = {}
        self.update_store()

    def update_store(self):
        url = f"https://{self._region}.{FACE_API_URL}/persongroups/{self._group}/persons?top=1000"
        payload={}
        headers = {
            'Content-Type': 'application/json',
            "Ocp-Apim-Subscription-Key": self._api_key,
        }
        response = requests.request("GET", url, headers=headers, data=payload)
        if response.status_code == requests.codes.ok:
            for person in response.json():
                self._store[person['personId']] = {"name": person['name'], "userData": person['userData']}

    def process_image(self, image):
        """Perform identify on a single image."""
        try:
            known_faces = []
            total = 0
            self.async_schedule_update_ha_state()
            headers = {"Ocp-Apim-Subscription-Key": self._api_key, "Content-Type": "application/octet-stream"}
            url = f"https://{self._region}.{FACE_API_URL}/detect?returnFaceId=true&recognitionModel={self._recognition_model}&returnRecognitionModel=false&detectionModel={self._detection_model}&faceIdTimeToLive=1000"
            headers = {
                'Content-Type': 'application/octet-stream',
                'Ocp-Apim-Subscription-Key': self._api_key
            }
            face_data = requests.request("POST", url, headers=headers, data=image).json()
            _LOGGER.error("Identify: %s", face_data)
            if face_data:
                face_ids = [data["faceId"] for data in face_data]
                url = f"https://{self._region}.{FACE_API_URL}/identify"
                payload = json.dumps({
                    "personGroupId": self._group,
                    "faceIds": face_ids,
                "maxNumOfCandidatesReturned": 10,
                    "confidenceThreshold": (self._confidence / 100)
                })
                headers = {
                    'Content-Type': 'application/json',
                    "Ocp-Apim-Subscription-Key": self._api_key,
                }
                person_data = requests.request("POST", url, headers=headers, data=payload).json()
                if person_data:
                    for face in person_data:
                        total += 1
                        if not face["candidates"]:
                            continue
                        data = face["candidates"][0]
                        name = ""
                        name = "" + self._store[data['personId']]['name']
                        # url = f"https://{self._region}.{FACE_API_URL}/persongroups/{self._group}/persons/{data['personId']}"
                        # payload={}
                        # person = requests.request("GET", url, headers=headers, data=payload).json()
                        # name = person['name']
                        known_faces.append(
                            {ATTR_NAME: name, ATTR_CONFIDENCE: data["confidence"] * 100}
                        )
            self.async_process_faces(known_faces, total)
        except HomeAssistantError as err:
            _LOGGER.error("Can't process image on Microsoft face: %s", err)
            return

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera_entity

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.ICON

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name