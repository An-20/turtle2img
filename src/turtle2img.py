"""
turtle2img
"""

import math
import turtle
import typing
import tkinter
import tempfile

from PIL import Image
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM


# ========================================================================
# property translation tables

CAP_STYLE_TRANSLATION = {
    "butt": "",  # butt: SVG default
    "round": "round",
    "projecting": "square",
    "": ""  # butt: default in Tk & SVG
}

JOIN_STYLE_TRANSLATION = {
    "bevel": "bevel",
    "miter": "",  # SVG default
    "round": "round"
}

TEXT_ANCHOR_TRANSLATION = {
    tkinter.constants.SE: "end",
    tkinter.constants.E: "end",
    tkinter.constants.NE: "end",

    tkinter.constants.SW: "",  # SVG default (value "start")
    tkinter.constants.W: "",
    tkinter.constants.NW: "",

    tkinter.constants.N: "middle",
    tkinter.constants.S: "middle",
    tkinter.constants.CENTER: "middle",
}

FONT_STYLE_TRANSLATION = {
    "italic": "italic",
    "roman": ""  # SVG default
}

FONT_WEIGHT_TRANSLATION = {
    "bold": "bold",
    "normal": ""  # SVG default
}


def set_canvas_size(
        width: int = 2000,
        height: int = 2000
) -> None:
    """
    Sets the canvas size

    :param width:
    :param height:
    :return:
    """
    if width * height >= 178956970:
        raise ValueError("Total number of pixels must be less than 178956970")
    screen = turtle.Screen()
    screen.screensize(width, height)


def get_html_color(
        canvas: tkinter.Canvas,
        color: str
) -> str:
    """returns Tk color in form '#rrggbb' or '#rgb'"""
    if color:
        # r, g, b \in [0..2**16]

        r, g, b = ["%02x" % (c // 256) for c in canvas.winfo_rgb(color)]

        if (r[0] == r[1]) and (g[0] == g[1]) and (b[0] == b[1]):
            # shorter form #rgb
            return "#" + r[0] + g[0] + b[0]
        else:
            return "#" + r + g + b
    else:
        return color


def linear_interpolate(
        p1: typing.Tuple[float, float],
        p2: typing.Tuple[float, float],
        t: float
) -> typing.Tuple[float, float]:
    xa, ya = p1
    xb, yb = p2
    return xa + t * (xb - xa), ya + t * (yb - ya)


def parse_dash(
        string: str,
        width: float
) -> typing.List[float]:
    """parse dash pattern specified with string"""

    # DashConvert from {tk-sources}/generic/tkCanvUtil.c
    w = max(1, int(width + 0.5))
    result = []
    for i, c in enumerate(string):
        if c == " " and len(result):
            result[-1] += w + 1
        elif c == "_":
            result.append(8 * w)
            result.append(4 * w)
        elif c == "-":
            result.append(6 * w)
            result.append(4 * w)
        elif c == ",":
            result.append(4 * w)
            result.append(4 * w)
        elif c == ".":
            result.append(2 * w)
            result.append(4 * w)
    return result


def font_actual(tkapp, font):
    """actual font parameters"""
    tmp = tkapp.call('font', 'actual', font)
    return dict(
        (tmp[i][1:], tmp[i + 1]) for i in range(0, len(tmp), 2)
    )


def font_metrics(tkapp, font, input_property=None):
    if input_property is None:
        tmp = tkapp.call('font', 'metrics', font)
        return dict(
            (tmp[i][1:], int(tmp[i + 1])) for i in range(0, len(tmp), 2)
        )
    else:
        return int(tkapp.call('font', 'metrics', font, '-' + input_property))


def set_attributes(element, **kwargs):
    for k, v in kwargs.items():
        element.setAttribute(k, str(v))
    return element


def arrow_head(
        document,
        x0,
        y0,
        x1,
        y1,
        arrow_shape
):
    """make arrow head at (x1,y1), arrow_shape is tuple (d1, d2, d3)"""
    dx = x1 - x0
    dy = y1 - y0

    poly = document.createElement('polygon')

    d = math.sqrt(dx * dx + dy * dy)
    if d == 0.0:  # XXX: equal, no "close enough"
        return poly

    try:
        d1, d2, d3 = list(map(float, arrow_shape))
    except ValueError:
        d1, d2, d3 = map(float, arrow_shape.split())

    p0 = (x0, y0)
    p1 = (x1, y1)

    xa, ya = linear_interpolate(p1, p0, d1 / d)
    xb, yb = linear_interpolate(p1, p0, d2 / d)

    t = d3 / d
    xc, yc = dx * t, dy * t

    points = [
        x1, y1,
        xb - yc, yb + xc,
        xa, ya,
        xb + yc, yb - xc,
    ]
    poly.setAttribute('points', ' '.join(map(str, points)))
    return poly


def make_svg_document():
    """Create default SVG document"""
    import xml.dom.minidom
    implementation = xml.dom.minidom.getDOMImplementation()
    doctype = implementation.createDocumentType(
        "svg", "-//W3C//DTD SVG 1.1//EN",
        "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"
    )
    document = implementation.createDocument(None, "svg", doctype)
    document.documentElement.setAttribute(
        "xmlns", 'http://www.w3.org/2000/svg'
    )
    return document


def convert_to_svg(
        document,
        canvas,
):
    """
    Convert 'items' stored in 'canvas' to SVG 'document'.

    Return list of XML elements
    """

    def get_property(name, default=""):
        if state == tkinter.constants.ACTIVE and options.get(state + name):
            return options.get(state + name)
        if state == tkinter.constants.DISABLED and options.get(state + name):
            return options.get(state + name)

        if options.get(name):
            return options.get(name)
        else:
            return default

    tk = canvas.tk

    items_to_convert = canvas.find_all()

    supported_item_types = {"line", "oval", "polygon", "rectangle", "text", "arc"}

    elements = []
    for item in items_to_convert:

        # skip unsupported items
        item_type = canvas.type(item)
        if item_type not in supported_item_types:
            continue

        # get item coordinates
        coordinates = canvas.coords(item)

        # get item options;
        # options is a dict: opt. name -> opt. actual value
        tmp = canvas.itemconfigure(item)
        options = dict((v0, v4) for v0, v1, v2, v3, v4 in tmp.values())

        # get state of item
        state = options["state"]
        if "current" in options["tags"]:
            options["state"] = tkinter.constants.ACTIVE
        elif options["state"] == "":
            options["state"] = "normal"
        else:
            # left state unchanged
            assert options["state"] in ["normal", tkinter.constants.DISABLED, "hidden"]

        # skip hidden items
        if options["state"] == 'hidden':
            continue

        if item_type == "line":
            options["outline"] = ""
            options["activeoutline"] = ""
            options["disabledoutline"] = ""

        elif item_type == 'arc' and options["style"] == tkinter.constants.ARC:
            options["fill"] = ""
            options["activefill"] = ""
            options["disabledfill"] = ""

        style = {
            "stroke": get_html_color(canvas, get_property("outline"))
        }

        if get_property("fill"):
            style["fill"] = get_html_color(canvas, get_property("fill"))
        else:
            style["fill"] = "none"

        width = float(options["width"])
        if state == tkinter.constants.ACTIVE:
            width = max(float(options["activewidth"]), width)
        elif state == tkinter.constants.DISABLED:
            try:
                disabled_width = options["disabledwidth"]
            except KeyError:
                # Text item might not have 'disabledwidth' option. This raises
                # the exception in course of processing of such item.
                # Default value is 0. Hence, it shall not affect width.
                pass
            else:
                if float(disabled_width) > 0:
                    width = disabled_width

        if width != 1.0:
            style['stroke-width'] = width

        if width:
            dash = canvas.itemcget(item, 'dash')
            if state == tkinter.constants.DISABLED and canvas.itemcget(item, 'disableddash'):
                dash = canvas.itemcget(item, 'disableddash')
            elif state == tkinter.constants.ACTIVE and canvas.itemcget(item, 'activedash'):
                dash = canvas.itemcget(item, 'activedash')

            if dash != '':
                try:
                    dash = tuple(map(int, dash.split()))
                except ValueError:
                    # int can't parse literal, dash defined with -.,_
                    line_width = float(get_property('width'))
                    dash = parse_dash(dash, line_width)

                style['stroke-dasharray'] = ",".join(map(str, dash))
                style['stroke-dashoffset'] = options['dashoffset']

        if item_type == 'line':
            # in this case, outline is set with fill property
            style["fill"], style["stroke"] = "none", style["fill"]

            style['stroke-linecap'] = CAP_STYLE_TRANSLATION[options['capstyle']]

            if options['smooth'] in ['1', 'bezier', 'true']:
                element = make_smooth_line(document, coordinates)

            elif options['smooth'] == 'raw':
                element = make_cubic_bezier(document, coordinates)

            elif options['smooth'] == '0':
                if len(coordinates) == 4:
                    # segment
                    element = make_segment(document, coordinates)

                else:
                    # polyline
                    element = make_polyline(document, coordinates)
                    style['fill'] = "none"
                    style['stroke-linejoin'] = JOIN_STYLE_TRANSLATION[options['joinstyle']]

            else:
                element = make_polyline(document, coordinates)
                style['stroke-linejoin'] = JOIN_STYLE_TRANSLATION[options['joinstyle']]

            elements.append(element)
            if options['arrow'] in [tkinter.constants.FIRST, tkinter.constants.BOTH]:
                arrow = arrow_head(
                    document,
                    coordinates[2],
                    coordinates[3],
                    coordinates[0],
                    coordinates[1],
                    options['arrow_shape']
                )
                arrow.setAttribute('fill', style['stroke'])
                elements.append(arrow)

            if options['arrow'] in [tkinter.constants.LAST, tkinter.constants.BOTH]:
                arrow = arrow_head(
                    document,
                    coordinates[-4],
                    coordinates[-3],
                    coordinates[-2],
                    coordinates[-1],
                    options['arrow_shape']
                )
                arrow.setAttribute('fill', style['stroke'])
                elements.append(arrow)

        elif item_type == 'polygon':
            if options['smooth'] in ['1', 'bezier', 'true']:
                element = make_smooth_polygon(document, coordinates)

            elif options['smooth'] == '0':
                element = make_polygon(document, coordinates)

            else:
                element = make_polygon(document, coordinates)

            elements.append(element)

            style['fill-rule'] = 'evenodd'
            style['stroke-linejoin'] = JOIN_STYLE_TRANSLATION[options['joinstyle']]

        elif item_type == 'oval':
            element = make_oval(document, coordinates)
            elements.append(element)

        elif item_type == 'rectangle':
            element = make_rectangle(document, coordinates)
            elements.append(element)

        elif item_type == 'arc':
            element = make_arc(document, coordinates, options['start'], options['extent'], options['style'])
            if options['style'] == tkinter.constants.ARC:
                style['fill'] = "none"

            elements.append(element)

        elif item_type == 'text':
            style['stroke'] = ''  # no stroke

            # setup geometry
            xmin, ymin, xmax, ymax = canvas.bbox(item)

            x = coordinates[0]

            # set y at 'dominant-baseline'
            y = ymin + font_metrics(tk, options['font'], 'ascent')

            element = set_attributes(
                document.createElement('text'),
                x=x, y=y
            )
            elements.append(element)

            element.appendChild(document.createTextNode(canvas.itemcget(item, 'text')))

            # 2. Setup style
            actual = font_actual(tk, options['font'])

            style['fill'] = get_html_color(canvas, get_property('fill'))
            style["text-anchor"] = TEXT_ANCHOR_TRANSLATION[options["anchor"]]
            style['font-family'] = actual['family']

            # starting from tkinter version 8.6 text can have an angle
            if 'angle' in options and tkinter.TkVersion >= 8.6:
                angle = float(options['angle'])
                if angle != 0:
                    # rotate to 0° to get correct bbox
                    canvas.itemconfigure(item, angle=0)
                    xmin, ymin, xmax, ymax = canvas.bbox(item)
                    # rotate back
                    canvas.itemconfigure(item, angle=angle)

                    # update y at the correct rotated position and keep
                    # y at 'dominant-baseline'
                    y = ymin + font_metrics(tk, options['font'], 'ascent')
                    element.setAttribute("y", str(y))
                    style['transform'] = "rotate(%s, %s, %s)" % (-angle, x, coordinates[1])

            # size
            size = float(actual['size'])
            if size > 0:  # size in points
                style['font-size'] = "%spt" % size
            else:  # size in pixels
                style['font-size'] = "%s" % (-size)

            style["font-style"] = FONT_STYLE_TRANSLATION[actual["slant"]]
            style["font-weight"] = FONT_WEIGHT_TRANSLATION[actual["weight"]]

            # overstrike/underline
            if actual["overstrike"] and actual["underline"]:
                style["text-decoration"] = "underline line-through"
            elif actual["overstrike"]:
                style["text-decoration"] = "line-through"
            elif actual["underline"]:
                style["text-decoration"] = "underline"

        for attr, value in style.items():
            if value != "":  # create only nonempty attributes
                element.setAttribute(attr, str(value))

    return elements


def save_png(
        filepath: str,
        margin=10,
) -> None:
    turtle.hideturtle()

    doc = make_svg_document()
    canvas = turtle.getcanvas()

    for element in convert_to_svg(doc, canvas):
        doc.documentElement.appendChild(element)

    bbox = canvas.bbox(tkinter.constants.ALL)
    if bbox is None:
        x1, y1, x2, y2 = 0, 0, 0, 0
    else:
        x1, y1, x2, y2 = bbox

    x1 -= margin
    y1 -= margin
    x2 += margin
    y2 += margin
    dx = x2 - x1
    dy = y2 - y1
    doc.documentElement.setAttribute("width", "%0.3f" % dx)
    doc.documentElement.setAttribute("height", "%0.3f" % dy)
    doc.documentElement.setAttribute(
        "viewBox", "%0.3f %0.3f %0.3f %0.3f" % (x1, y1, dx, dy))

    temp_file_1 = tempfile.NamedTemporaryFile()
    temp_file_1.write(doc.toxml().encode("UTF-8"))
    temp_file_1.seek(0)
    drawing = svg2rlg(temp_file_1.name)

    renderPM.drawToFile(drawing, filepath, fmt="PNG")


def save_jpg(
        filepath: str,
        margin=10,
) -> None:
    turtle.hideturtle()

    doc = make_svg_document()
    canvas = turtle.getcanvas()

    for element in convert_to_svg(doc, canvas):
        doc.documentElement.appendChild(element)

    bbox = canvas.bbox(tkinter.constants.ALL)
    if bbox is None:
        x1, y1, x2, y2 = 0, 0, 0, 0
    else:
        x1, y1, x2, y2 = bbox

    x1 -= margin
    y1 -= margin
    x2 += margin
    y2 += margin
    dx = x2 - x1
    dy = y2 - y1
    doc.documentElement.setAttribute("width", "%0.3f" % dx)
    doc.documentElement.setAttribute("height", "%0.3f" % dy)
    doc.documentElement.setAttribute(
        "viewBox", "%0.3f %0.3f %0.3f %0.3f" % (x1, y1, dx, dy))

    temp_file_1 = tempfile.NamedTemporaryFile()
    temp_file_1.write(doc.toxml().encode("UTF-8"))
    temp_file_1.seek(0)
    drawing = svg2rlg(temp_file_1.name)

    temp_file_2 = tempfile.NamedTemporaryFile()
    renderPM.drawToFile(drawing, temp_file_2.name, fmt="PNG")
    img = Image.open(temp_file_2.name)  # use PIL to load and save to jpg
    img.load()  # required for png.split()
    background = Image.new("RGB", img.size, (255, 255, 255))
    if len(img.split()) == 4:
        background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
        background.save(
            filepath,
            format="jpeg"
        )
    else:
        img.save(
            filepath,
            format="jpeg"
        )


# make stuff
# ========================================

def make_smooth_line(
        document,
        coordinates
):
    """smoothed polyline"""
    element = document.createElement("path")
    path = []

    points = [(coordinates[i], coordinates[i + 1]) for i in range(0, len(coordinates), 2)]

    def pt(input_points):
        x0, y0 = input_points[0]
        x1, y1 = input_points[1]
        p0 = (2 * x0 - x1, 2 * y0 - y1)

        x0, y0 = input_points[-1]
        x1, y1 = input_points[-2]
        pn = (2 * x0 - x1, 2 * y0 - y1)

        p = [p0] + input_points[1:-1] + [pn]

        for i in range(1, len(input_points) - 1):
            last_point = p[i - 1]
            this_point = p[i]
            next_point = p[i + 1]

            yield (
                linear_interpolate(last_point, this_point, 0.5),
                this_point,
                linear_interpolate(this_point, next_point, 0.5)
            )

    for i, (a, b, c) in enumerate(pt(points)):
        if i == 0:
            path.append("M%s,%s Q%s,%s %s,%s".format(a[0], a[1], b[0], b[1], c[0], c[1]))
        else:
            path.append("T%s,%s".format(c[0], c[1]))

    element.setAttribute("d", " ".join(path))
    return element


def make_cubic_bezier(
        document,
        coordinates
):
    """cubic bezier polyline"""
    element = document.createElement('path')
    points = [(coordinates[i], coordinates[i + 1]) for i in range(0, len(coordinates), 2)]
    path = ["M%s %s" % points[0]]
    for n in range(1, len(points), 3):
        a, b, c = points[n:n + 3]
        path.append("C%s,%s %s,%s %s,%s" % (a[0], a[1], b[0], b[1], c[0], c[1]))
    element.setAttribute('d', ' '.join(path))
    return element


def make_segment(document, coordinates):
    """polyline with 2 vertices using <line> tag"""
    return set_attributes(
        document.createElement('line'),
        x1=coordinates[0],
        y1=coordinates[1],
        x2=coordinates[2],
        y2=coordinates[3],
    )


def make_polyline(document, coordinates):
    """polyline with more than 2 vertices"""
    points = []
    for i in range(0, len(coordinates), 2):
        points.append("%s,%s" % (coordinates[i], coordinates[i + 1]))
    return set_attributes(
        document.createElement('polyline'),
        points=' '.join(points),
    )


def make_smooth_polygon(document, coordinates):
    """smoothed filled polygon"""

    element = document.createElement('path')
    path = []
    points = [(coordinates[i], coordinates[i + 1]) for i in range(0, len(coordinates), 2)]

    def pt(input_points):
        p = input_points
        n = len(input_points)
        for i in range(0, len(input_points)):
            last_point = p[(i - 1) % n]
            this_point = p[i]
            next_point = p[(i + 1) % n]

            yield (
                linear_interpolate(last_point, this_point, 0.5),
                this_point,
                linear_interpolate(next_point, next_point, 0.5)
            )

    for i, (A, B, C) in enumerate(pt(points)):
        if i == 0:
            path.append("M%s,%s Q%s,%s %s,%s" % (A[0], A[1], B[0], B[1], C[0], C[1]))
        else:
            path.append("T%s,%s" % (C[0], C[1]))

    path.append("z")

    element.setAttribute('d', ' '.join(path))
    return element


def make_polygon(document, coordinates):
    """filled polygon"""
    points = []
    for i in range(0, len(coordinates), 2):
        points.append("%s,%s" % (coordinates[i], coordinates[i + 1]))

    return set_attributes(
        document.createElement('polygon'),
        points=' '.join(points)
    )


def make_oval(document, coordinates):
    """circle/ellipse"""
    x1, y1, x2, y2 = coordinates
    # circle
    if x2 - x1 == y2 - y1:
        return set_attributes(
            document.createElement('circle'),
            cx=(x1 + x2) / 2,
            cy=(y1 + y2) / 2,
            r=abs(x2 - x1) / 2,
        )
    # ellipse
    else:
        return set_attributes(
            document.createElement('ellipse'),
            cx=(x1 + x2) / 2,
            cy=(y1 + y2) / 2,
            rx=abs(x2 - x1) / 2,
            ry=abs(y2 - y1) / 2,
        )


def make_rectangle(document, coordinates):
    element = document.createElement('rect')
    return set_attributes(
        element,
        x=coordinates[0],
        y=coordinates[1],
        width=coordinates[2] - coordinates[0],
        height=coordinates[3] - coordinates[1],
    )


def make_arc(
        document,
        bounding_rect,
        start,
        extent,
        style
):
    """arc, pieslice (filled), arc with chord (filled)"""
    (x1, y1, x2, y2) = bounding_rect
    import math

    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0

    rx = (x2 - x1) / 2.0
    ry = (y2 - y1) / 2.0

    start = math.radians(float(start))
    extent = math.radians(float(extent))

    # from SVG spec:
    # http://www.w3.org/TR/SVG/implnote.html#ArcImplementationNotes
    x1 = rx * math.cos(start) + cx
    y1 = -ry * math.sin(start) + cy  # XXX: ry is negated here

    x2 = rx * math.cos(start + extent) + cx
    y2 = -ry * math.sin(start + extent) + cy  # XXX: ry is negated here

    if abs(extent) > math.pi:
        fa = 1
    else:
        fa = 0

    if extent > 0.0:
        fs = 0
    else:
        fs = 1

    path = ['M%s,%s' % (x1, y1), 'A%s,%s 0 %d %d %s,%s' % (rx, ry, fa, fs, x2, y2)]
    # common: arc

    if style == tkinter.ARC:
        pass

    elif style == tkinter.CHORD:
        path.append('z')

    else:  # default: pieslice
        path.append('L%s,%s' % (cx, cy))
        path.append('z')

    return set_attributes(document.createElement('path'), d=''.join(path))
