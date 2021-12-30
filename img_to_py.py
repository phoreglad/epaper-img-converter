from PIL import Image
import argparse
from pathlib import Path


THR = "Set threshold values.\nRequires one value for L1 and three for L2 mode.\nUse this as the last argument"
MODE = "Output image format:\nL1 - binary (black and white) [default]\nL2 - 4 level grayscale"
WIDTH = "Set desired target image width.\nIf no --height argument is specified the image\n" \
        "will be uniformly scaled to this width."
HEIGHT = "Set desired target image height.\nIf no --width argument is specified the image\n" \
         "will be uniformly scaled to this height."

parser = argparse.ArgumentParser(prog="E-paper image converter", formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("source", type=str, help="File to convert")
parser.add_argument("target", type=str, nargs="?", help="Target file")
parser.add_argument("-m", "--mode", choices=("L1", "L2"), default="L1", help=MODE)
parser.add_argument("-p", "--preview", action="store_true", help="Show image preview")
parser.add_argument("--preview-only", action="store_true", help="Show image preview and exit without saving data")
parser.add_argument("-d", "--dither", action="store_true", help="Enable dithering")
parser.add_argument("-t", "--threshold", type=int, nargs="+", default=[63, 126, 189], help=THR)
parser.add_argument("--width", type=int, help=WIDTH)
parser.add_argument("--height", type=int, help=HEIGHT)

args = parser.parse_args()


def thr(px):
    if px < args.threshold[0]:
        return 0
    elif args.threshold[0] <= px < args.threshold[1]:
        return 85
    elif args.threshold[1] <= px < args.threshold[2]:
        return 170
    else:
        return 255


data_bw = None
data_red = None

img = Image.open(args.source)

# Get rid of alpha and change it to white.
if img.mode == "RGBA":
    tmp = Image.new("RGBA", img.size, "WHITE")
    tmp.paste(img, mask=img)
    img = tmp.convert("RGB")

# Scale image according to provided arguments.
if args.width is not None and args.height is not None:
    img = img.resize((args.width, args.height))
    print(f"Scaled to {args.width}x{args.height}")
elif args.width is not None:
    w, h = img.size
    ratio = h / w
    img = img.resize((args.width, int(args.width * ratio)))
    print(f"Scaled uniformly to: {args.width}x{int(args.width * ratio)}")
elif args.height is not None:
    w, h = img.size
    ratio = w / h
    img = img.resize((int(args.height * ratio), args.height))
    print(f"Scaled uniformly to: {int(args.height * ratio)}x{args.height}")
else:
    pass

# Pad image to make width divisible by 8.
w, h = img.size
if w % 8 != 0:
    w = w + 8 - w % 8
    print(f"Image width not divisible by 8. Padded to width: {w}")
    tmp = Image.new(img.mode, (w, h), (255, 255, 255))
    tmp.paste(img)
    img = tmp

# BW image conversion.
if args.mode == "L1":
    if args.dither:
        # Using "1" mode with dithering gives better results.
        img = img.convert("1").point(lambda p: p > args.threshold[0] and 255)
        if args.preview_only:
            img.show()
            exit()
        # In this mode data match FrameBuffer HLSB format, no need for further processing.
        data_bw = bytearray(img.tobytes())
    else:
        # Using "L" mode makes thresholding easier.
        img = img.convert("L").point(lambda p: p > args.threshold[0] and 255)
        if args.preview_only:
            img.show()
            exit()

        # Convert pixel data to HLSB format.
        img_data = img.tobytes()
        data_bw = bytearray(w * h // 8)
        for byte in range(w * h // 8):
            pixels = img_data[byte * 8:(byte + 1) * 8]
            tmp = 0
            for i, v in enumerate(pixels):
                tmp |= (v & 0x1) << (7 - i)
            data_bw[byte] = tmp

# 4 level grayscale conversion.
else:
    # Converting to "P" mode first allows dithering.
    img = img.convert("P", dither=Image.FLOYDSTEINBERG if args.dither else Image.NONE).convert("L").point(thr)
    if args.preview_only:
        img.show()
        exit()

    # Convert pixel data to bytearrays for BW and RED RAMs in HLSB format.
    data_bw = bytearray(w * h // 8)
    data_red = bytearray(w * h // 8)
    img_data = img.tobytes()
    for byte in range(w * h // 8):
        pixels = img_data[byte * 8:(byte + 1) * 8]
        tmp_bw = 0
        tmp_red = 0
        for i, v in enumerate(pixels):
            tmp_bw |= (v & 0x1) << (7 - i)
            tmp_red |= ((v >> 1) & 0x1) << (7 - i)
        data_bw[byte] = tmp_bw
        data_red[byte] = tmp_red

# Save file.
if args.target is None:
    out_file = Path(args.source).stem + ".py"
else:
    if args.target.split(".")[-1].lower() != ".py":
        out_file = args.target + ".py"
    else:
        out_file = args.target
print(f"Saving data to: {out_file}")
with open(out_file, "w") as f:
    f.write(f"width = {w}\n")
    f.write(f"height = {h}\n")
    f.write(f"img_bw = {data_bw}\n")
    # Save data for RED RAM only if it exists.
    if data_red:
        f.write(f"img_red = {data_red}\n")

# Show preview if requested.
if args.preview:
    img.show()
