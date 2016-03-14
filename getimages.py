import Image
import piexif
import urllib
import urllib2
import json
import os
import base64

from googleapiclient import discovery
import httplib2
from oauth2client.client import GoogleCredentials

imageurl = 'http://fedoraproxy.lib.virginia.edu/fedora/objects/***PID***/methods/djatoka:StaticSDef/getScaled?maxWidth=24000&maxHeight=24000'
searchurl = 'http://search.lib.virginia.edu/catalog.json?f%5Bformat_facet%5D%5B%5D=Photograph&f%5Bsource_facet%5D%5B%5D=UVA+Library+Digital+Repository&q=&search_field=keyword&sort=date_received_facet+desc&page='
workdir = 'work'

page = 1
resultsLeft = None

DISCOVERY_URL='https://{api}.googleapis.com/$discovery/rest?version={apiVersion}'
def get_vision_service():
    credentials = GoogleCredentials.get_application_default()
    return discovery.build('vision', 'v1', credentials=credentials,
                           discoveryServiceUrl=DISCOVERY_URL)

def vis_image(face_file):
    """Uses the Vision API to detect faces in the given file.
    Args:
        face_file: A file-like object containing an image with faces.
    Returns:
        An array of dicts with information about the faces in the picture.
    """
    image_content = face_file.read()
    batch_request = [{
        'image': {
            'content': base64.b64encode(image_content)
            },
        'features': [
            { 'type': 'FACE_DETECTION' },
            { 'type': 'TEXT_DETECTION' },
            { 'type': 'LANDMARK_DETECTION' },
            { 'type': 'LOGO_DETECTION' },
            { 'type': 'SAFE_SEARCH_DETECTION' },
            { 'type': 'IMAGE_PROPERTIES' },
            { 'type': 'LABEL_DETECTION' }
        ]
        }]

    service = get_vision_service()
    request = service.images().annotate(body={
        'requests': batch_request,
        })
    response = request.execute()

    return response['responses'][0]

# Walk through the pages of results
while resultsLeft is None or resultsLeft > 0:
  response = urllib2.urlopen(searchurl+str(page))
  data = json.load(response)

  # Walk through the results
  for item in data['response']['docs']:
    print item['id']

    # Get the image if we don't already have it
    imageURL = imageurl.replace('***PID***',item['id']) 
    destPath = workdir + '/' + item['id']+'.jpg'

    if not os.path.exists(destPath):
      if not os.path.exists(workdir):
        os.makedirs(workdir)

      urllib.urlretrieve(imageURL, destPath) 

    # Submit Image to google for visualize processing
    metafile = destPath+'.json'
    if not os.path.exists(metafile):
      with open(destPath, 'rb') as image:
        extra = vis_image(image)
        if extra.get('faceAnnotations',None) is not None:
          faces = extra['faceAnnotations']
          print('Found %s face%s' % (len(faces), '' if len(faces) == 1 else 's'))    
        item['extra']=extra
    else:
      item = json.load(open(metafile))

    # Stuff the meta from the result into the image so we don't lose it
    im = Image.open(destPath)
    exif_dict = {"0th":{}, "Exif":{}, "GPS":{}} 
    exif_dict["Exif"][piexif.ExifIFD.UserComment] = json.dumps(item)
    exif_bytes = piexif.dump(exif_dict)
    im.save(destPath, "jpeg", exif=exif_bytes)
    meta_file = open(metafile,'w')
    json.dump(item, meta_file, indent=4)

  resultsLeft = data['response']['numFound'] - data['response']['start'] + len(data['response']['docs']) 
  page = page+1
