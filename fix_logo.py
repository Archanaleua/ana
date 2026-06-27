from PIL import Image

def remove_bg(input_path, output_path, bg_color):
    img = Image.open(input_path).convert("RGBA")
    pixels = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = pixels[x, y]
            if bg_color == 'black' and r < 40 and g < 40 and b < 40:
                pixels[x, y] = (0, 0, 0, 0)
            elif bg_color == 'white' and r > 220 and g > 220 and b > 220:
                pixels[x, y] = (0, 0, 0, 0)
    img.save(output_path, "PNG")

remove_bg("static/img/logo-dark.png",  "static/img/logo-dark.png",  "black")
remove_bg("static/img/logo-light.png", "static/img/logo-light.png", "white")
print("Done! Backgrounds removed.")