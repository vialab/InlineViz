from apiclient.discovery import build
import json
import numpy as np
import pandas as pd

def g_translate(source, google_key):
    # AIzaSyB5RSAZ4G_qmZ_oUlyqbwqZiZGY6WHV1D4
    service = (build('translate', 'v2', developerKey=google_key))
    request = service.translations().list(q=source, target='fr')
    response = request.execute()

    return response['translations'][0]['translatedText']

def __str__(self):
    return unicode(self).encode('utf-8')

#sentence = g_translate('The earth')
#sentence = __str__(sentence)

#print sentence
