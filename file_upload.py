import sys
sys.path.append('./static/py')
import io
import os
from flask import Flask, request, redirect, url_for,send_from_directory,render_template,jsonify, send_file, session, jsonify
from flask_babel import Babel
from werkzeug.utils import secure_filename
import numpy as np
from PIL import Image
import base64
import re
# import cStringIO
import imp
import pdf_text_extraction
import pickle as pickle
import pickle_session as ps
import json
import wand.image as wi
from textension import Block, Textension
from html.parser import HTMLParser
from input_text_processing import *

UPLOAD_FOLDER = './uploads/'
ALLOWED_EXTENSIONS = set(['bmp', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'super secret key and diceroll: 12'
app.config['SESSION_TYPE'] = 'filesystem'
app.session_interface = ps.PickleSessionInterface("./app_session")

babel = Babel(app)

h = HTMLParser()

default_options = {
    "spread":20,
    "hires":True,
    "cut":5,
    "noise":25,
    "buffer":1,
    "width":1024,
    "height":1024,
    "translate": False,
    "antialias": True,
    "blur":0,
    "google_key":"",
    "horizontal_spread": 500,
    "margin_size": 100, 
    "stripe_bg": False, 
    "multi_column": True
}

LANGUAGES = list(set(["en", "fr"]))  # list of set removes duplicates
# Select the language to use

@babel.localeselector
def get_locale():
    if request.cookies.get("selected-language", None):
        language = request.cookies.get("selected-language")
    else:
        language = request.accept_languages.best_match(LANGUAGES)
    return language
    
@app.route('/', methods=['GET', 'POST'])
def index():
    if "options" not in session:
        session["options"] = default_options
    return render_template('index.html')

@app.route('/return_file')
def return_file():
    return send_file("./file_processing/ocr_document.pdf"
                    , attachment_filename="ocr_document.pdf")

@app.route('/interact')
@app.route('/interact/<page_no>')
def interact(page_no=0):
    """ Web hook that will load all the data processed from /upload """
    # samples are pre-processed and pickled for easy loading
    sample = request.args.get("sample")
    if sample is not None:
        if sample == "a_mad_tea_party":
            sample = "./server/a_mad_tea_party.pkl"
        if sample == "textension":
            sample = "./server/textension.pkl"
        if sample == "southern_life":
            sample = "./server/southern_life.pkl"
        with open(sample, 'rb') as f:
            session["vis"] = pickle.load(f,encoding='bytes')
    # if we don't have a vis to render, redirect back home
    if "vis" not in session:
        return redirect(url_for("index"))
    # default to first page
    try:
        page_no = int(page_no)-1
    except:
        page_no = 0
    if page_no >= len(session["vis"]):
        page_no = 0

    # looping through the full arrays during rendering is slow due to size
    # segregate the data to matrices and do not include images
    vis = session["vis"][page_no]
    image_mesh = formatToMatrix(vis.mesh)

    image_text = []
    image_patches = []
    image_patch_space = []
    image_space = []
    image_dim = []
    image_coords = []
    bounding_boxes = []
    word_blocks = []
    ngram_plot = []
    ocr_text = []
    ocr_translated = []
    block_size = []

    for b in vis.blocks:
        image_text.append(formatToMatrix(b.img_text))
        image_patches.append(formatToMatrix(b.img_patches))
        image_patch_space.append(formatToMatrix(b.img_patch_space))
        image_space.append(formatToMatrix(b.img_space))
        image_dim.append(b.chop_dimension)
        image_coords.append(b.img_coords)
        bounding_boxes.append(b.bounding_boxes)
        word_blocks.append(b.word_blocks)
        ngram_plot.append(b.ngram_plot)
        ocr_text.append(b.ocr_text)
        ocr_translated.append(b.ocr_translated)
        block_size.append([b.img_width, b.img_height])

    return render_template('interact.html'
        , image_text=image_text
        , image_patches=image_patches
        , image_space=image_space
        , image_patch_space=image_patch_space
        , mesh=image_mesh
        , block_size=block_size
        , image_dim=image_dim
        , image_coords=image_coords
        , bounding_boxes=bounding_boxes
        , word_blocks=json.dumps(word_blocks)
        , ngram_plot=json.dumps(ngram_plot)
        # , ocr=json.dumps([h.unescape(line) for line in ocr_text])
        , ocr=json.dumps(ocr_text)
        , translation=json.dumps([h.unescape(line) for line in ocr_translated])
        , page_no=page_no
        , num_pages=len(session["vis"])
        , num_blocks=len(vis.blocks)
        , image_size=[vis.img_width, vis.img_height]
        , bg_color=vis.bg_color
        )


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """ Receive images from the dropzone and process it. Processed data is
     saved to the session and used later on for rendering in JINJA2 """
    if request.method == 'POST':
        file = request.files['file']

        if file and allowed_file(file.filename):
            savevisSessionArgs(request.form)
            file_extension = file.filename.split(".")[-1].lower()
            
            vis_list = []
            if file_extension == "pdf":
                # need to split pages and decompose one by one
                pdf_pages = pdfSplitPageStream(file.stream)
                for page in pdf_pages:
                    page.seek(0)
                    vis = Textension(page, _translate=session["options"]["translate"]
                                , _vertical_spread=session["options"]["spread"]
                                , _hi_res=session["options"]["hires"]
                                , _anti_alias=session["options"]["antialias"]
                                , _pixel_cut_width=session["options"]["cut"]
                                , _noise_threshold=session["options"]["noise"]
                                , _line_buffer=session["options"]["buffer"]
                                , _blur=session["options"]["blur"]
                                , _google_key=session["options"]["google_key"]
                                , _max_size=(session["options"]["width"],session["options"]["height"])
                                , _margin_size=session["options"]["margin_size"]
                                , _stripe_bg=session["options"]["stripe_bg"]
                                , _blockify_page=session["options"]["multi_column"])
                    vis.blockify()
                    vis_list.append(vis)
            else:
                # just an image
                vis = Textension(file.stream
                                , _translate=session["options"]["translate"]
                                , _hi_res=session["options"]["hires"]
                                , _anti_alias=session["options"]["antialias"]
                                , _vertical_spread=session["options"]["spread"]
                                , _pixel_cut_width=session["options"]["cut"]
                                , _noise_threshold=session["options"]["noise"]
                                , _line_buffer=session["options"]["buffer"]
                                , _blur=session["options"]["blur"]
                                , _google_key=session["options"]["google_key"]
                                , _max_size=(session["options"]["width"],session["options"]["height"])
                                , _margin_size=session["options"]["margin_size"]
                                , _stripe_bg=session["options"]["stripe_bg"]
                                , _blockify_page=session["options"]["multi_column"])
                vis.blockify()
                vis_list.append(vis)

            session["vis"] = vis_list
            # with open("./a_mad_tea_party.pkl", "w+") as f:
            #     pickle.dump(vis_list, f)
    
    if "options" not in session:
        session["options"] = default_options
    return render_template('upload.html')
    # return redirect(url_for("index"))


@app.route('/hook', methods=['POST'])
def get_image():
    """ Retrieves image that was taken by the webcam, and processes like /upload """
    vis_list=[]
    savevisSessionArgs(request.values)
    image_b64 = re.sub("data:image/png;base64,", "", request.values["imageBase64"])
    bImage = io.BytesIO(base64.b64decode(image_b64))
    img = Image.open(bImage)
    img = img.crop((133,5,499,img.size[1]-5))
    bImage = io.BytesIO()
    img.save(bImage, "PNG")
    bImage.seek(0)
    vis = Textension(bImage
                    , _translate=session["options"]["translate"]
                    , _hi_res=session["options"]["hires"]
                    , _anti_alias=session["options"]["antialias"]
                    , _vertical_spread=session["options"]["spread"]
                    , _pixel_cut_width=session["options"]["cut"]
                    , _noise_threshold=session["options"]["noise"]
                    , _line_buffer=session["options"]["buffer"]
                    , _blur=session["options"]["blur"]
                    , _google_key=session["options"]["google_key"]
                    , _max_size=(session["options"]["width"],session["options"]["height"])
                    , _margin_size=session["options"]["margin_size"]
                    , _stripe_bg=session["options"]["stripe_bg"]
                    , _blockify_page=session["options"]["multi_column"])
    # vis.decompose()
    vis.blockify()
    vis_list.append(vis)
    session["vis"] = vis_list
    return redirect(url_for("interact"))



##### HELPER FUNCTIONS
def savevisSessionArgs(form):
    """ Save visualization parameters into session"""
    if "options" not in session:
        session["options"] = default_options
        
    options_form = session["options"]
    for option in form:
        if option not in options_form:
            # don't save unnecessary data
            continue
        if option == "translate" or option == "hires" or option == "antialias" \
        or option == "stripe_bg" or option == "multi_column":
            if form[option] == "true":
                options_form[option] = True
            else:
                options_form[option] = False
            continue
        if option == "google_key":
            options_form[option] = form[option]
        else:
            options_form[option] = int(form[option])

    session["options"] = options_form


def allowed_file(filename):
    """ check if the uploaded file extension is allowed """
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS
       

def formatToMatrix(data):
    """ Itemize our data into dict multi-d arrays for consistency 
     and efficiency by filtering out the images """
    if len(data) == 0:
        return []
    new_array = []
    for row in data:
        item = []
        for col in row:
            item.append(dict((i,col[i]) for i in col if i!="img"))
        new_array.append(item)
    return new_array

if __name__ == "__main__":
    sess.init_app(app)
    app.run(threaded=True)