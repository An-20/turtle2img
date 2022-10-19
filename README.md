Turtle to png / jpg exporter
========================================================================

This is a fork of WojciechMula/canvas2svg which uses svglib, reportlab and
Pillow to convert things drawn in Python's turtle library to png or jpg files.

The list of supported items is the same as canvas2svg.

Supported items:

* lines
* lines with arrows
* polygons
* smoothed lines and polygons
* ovals (i.e. circle & ellipse)
* arcs (all kind, i.e. ARC, CHORD, PIESLICE)
* rectangles
* text (**unwrapped** only i.e. attribute width = 0)

Unsupported items:

* images
* bitmaps
* windows

Stipples are not applied.


Public functions
------------------------------------------------------------------------

save_png(filepath: str, margin=10) -> None:

* filepath: The filepath to save the output image to
* margin: The number of pixels around the bounding box of image elements to include


save_jpg(filepath: str, margin=10) -> None:

* filepath: The filepath to save the output image to
* margin: The number of pixels around the bounding box of image elements to include

Original repository: https://github.com/WojciechMula/canvas2svg
