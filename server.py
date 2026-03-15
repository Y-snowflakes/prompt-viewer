import os
import json
import threading
from flask import Flask, render_template, request, send_from_directory
from PIL import Image
import piexif
import piexif.helper
import re

EXTS = (".png",".jpg",".jpeg",".webp")

app = Flask(__name__)

PRELOAD = 200


def index_file(folder):

    return os.path.join(folder,"prompt_index.json")


def read_prompt(path):

    try:

        im = Image.open(path)

        if "parameters" in im.info:
            return im.info["parameters"]

        exif = im.info.get("exif")

        if exif:

            exif_dict = piexif.load(exif)

            comment = exif_dict["Exif"].get(
                piexif.ExifIFD.UserComment
            )

            if comment:
                return piexif.helper.UserComment.load(comment)

    except:
        pass

    return ""

def split_prompt(text):

    prompt = ""
    negative = ""
    others = ""

    if "Negative prompt:" in text:

        parts = text.split("Negative prompt:",1)

        prompt = parts[0].strip()

        rest = parts[1]

        if "Steps:" in rest:

            neg,other = rest.split("Steps:",1)

            negative = neg.strip()

            others = "Steps:" + other.strip()

        else:

            negative = rest.strip()

    else:

        prompt = text

    return {
        "prompt":prompt,
        "negative":negative,
        "others":others
    }


def build_index(folder):

    items = []

    for root,dirs,files in os.walk(folder):

        for file in files:

            if file.lower().endswith(EXTS):

                path = os.path.join(root,file)

                rel = os.path.relpath(path,folder)

                raw = read_prompt(path)

                data = split_prompt(raw)

                items.append({
                    "image":rel.replace("\\","/"),
                    "prompt":data["prompt"],
                    "negative":data["negative"],
                    "others":data["others"]
                })

    with open(index_file(folder),"w",encoding="utf8") as f:

        json.dump(items,f,ensure_ascii=False)

def preload_images(folder):
    items = []
    count = 0
    for root,dirs,files in os.walk(folder):
        for file in files:
            if file.lower().endswith(EXTS):
                path = os.path.join(root,file)
                rel = os.path.relpath(path,folder)
                raw = read_prompt(path)
                data = split_prompt(raw)  # ←これが必要
                items.append({
                    "image": rel.replace("\\","/"),
                    "prompt": data["prompt"],
                    "negative": data["negative"],
                    "others": data["others"]
                })
                count += 1
                if count >= PRELOAD:
                    return items
    return items


def load_images(folder):

    idx = index_file(folder)

    if os.path.exists(idx):

        with open(idx,"r",encoding="utf8") as f:
            return json.load(f)

    # indexがない場合
    items = preload_images(folder)

    # 裏で作る
    threading.Thread(
        target=build_index,
        args=(folder,),
        daemon=True
    ).start()

    return items

def split_keywords(q):

    pattern = r'"([^"]+)"|(\S+)'
    words = re.findall(pattern,q)

    result = []

    for w in words:

        if w[0]:
            result.append(w[0])
        else:
            result.append(w[1])

    return result


@app.route("/")
def index():
    folder = request.args.get("dir", "").strip()
    folder = os.path.normpath(folder) if folder else ""  # 空文字なら "" にする

    q = request.args.get("q", "").lower()

    images = []
    if folder and os.path.exists(folder):
        images = load_images(folder)
        if q:
            keywords = split_keywords(q.lower())
            images = [
                i for i in images
                if all(k in i["prompt"].lower() for k in keywords)
            ]

    return render_template(
        "index.html",
        images=images,
        folder=folder,  # ここで空文字が渡る
        query=q
    )


@app.route("/images")
def images():

    folder = request.args.get("dir")
    filename = request.args.get("file")

    return send_from_directory(folder,filename)


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )