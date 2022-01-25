# Home-Assistant-MicrosoftVision
This custom integration calls the Microsoft Azure Cognitive services Vision API https://azure.microsoft.com/en-us/services/cognitive-services/#api

## Setup
Get the service endpoint and key, follow these instructions https://docs.microsoft.com/en-us/azure/search/search-get-started-postman

## Installation
Copy all the files from this repo, to your custom_component folder

## Configuration
Add to your configuration yaml:

```yaml
image_processing:
  - platform: microsoft_face_identity
    api_key: <your api key>
    azure_region: <your full endpoint>
    group: <Person group>
    recognition_model: "recognition_1"
    detection_model: "detection_1"
    confidence: 80
    source:
      - entity_id: camera.door
```
