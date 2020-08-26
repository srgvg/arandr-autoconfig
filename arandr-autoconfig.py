#!/usr/bin/env python3
import click
import tendo.singleton
import time
import os.path
import subprocess
import re
import base64
import hashlib
import datetime


def _debug(msg):

    msg = str(msg)
    message = [str(timestamp()), "DEBUG", msg]
    print(" ".join(message))


def timestamp(ts=None):

    if ts:
        ts = int(ts)
    else:
        ts = time.time()
    return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')


def parse_xrandr_output(text):

    pattern = re.compile(r"^([\w-]+)\sconnected\s(primary)?\s?([0-9+x]+)?\s?(left|right)?.*")
    ret = filter(lambda x: pattern.match(x), text.decode("utf-8").splitlines())
    ret = map(lambda x: pattern.match(x).group(1,2,3,4), ret)
    displays = sorted(ret, key= lambda x: x[0])
    dimpattern = re.compile(r"([0-9]+)x([0-9]+)[+]([0-9]+)[+]([0-9]+)")
    displayslist=[]

    for display in displays:
        display = list(display)
        try:
            dimension = dimpattern.match(display[2])
            w, h, x, y = dimension.group(1,2,3,4)
            ratio = int(w) / int(h)
            orientation=display.pop()
            if ratio > 2:
                if orientation in ("left", "right"): # portrait
                    display.append('portrait')
                    display.append('splitv')
                else:
                    display.append('ultrawide')
                    display.append('splith')
            elif ratio > 0:
                if orientation in ("left", "right"): # portrait
                    display.append('portrait')
                    display.append('splitv')
                else:
                    display.append('landscape')
                    display.append('tabbed')

        except TypeError:
            display.append(None)
            display.append(None)
        displayslist.append(display)
    displays = displayslist
    return displays


def order_displays(displays):

    # order displays from left to right, top to bottom
    # smallest return number comes first
    def _xsort(item):
        if item[2]:
            dimpattern = re.compile(r"([0-9]+)x([0-9]+)[+]([0-9]+)[+]([0-9]+)")
            dimension = dimpattern.match(item[2])
            [w, h, x, y] = [ int(_) for _ in dimension.group(1,2,3,4)]
            #order = x + w + y
            #print(item[0], "\t", w, h, x, y, "\t", order, "\t", (y+1)*x)
            order = (y + 1) * x
            return order
        else:
            return 0
    ret = sorted(displays, key=_xsort)
    print(timestamp(), " Ordered:     ", ret)
    # now, keep the primary screen first, and rotate the ones before it to the
    # end
    for item in ret.copy():
        if item[1] == "primary":
            break
        else:
            ret.append(ret.pop(0))
    return ret


def current_connected_displays(primary=False):

    proc = subprocess.run(["xrandr"], stdout=subprocess.PIPE)
    output = proc.stdout
    ret = parse_xrandr_output(output)
    if primary:
        ret = order_displays(ret)
    return ret


def get_edid():

    def _hash(string):
        hasher = hashlib.sha1(string)
        return base64.urlsafe_b64encode(hasher.digest()).decode("utf-8")[:10]

    _xrandr = """xrandr -q --verbose | awk '/^[^ ]+ (dis)?connected / { DEV=$1; } $1 ~ /^[a-f0-9]+$/ { ID[DEV] = ID[DEV] $1 } END { for (X in ID) { print X "," ID[X]; } }'"""
    process = subprocess.Popen(_xrandr, stdout=subprocess.PIPE, shell=True)
    output, error = process.communicate()
    dispedid = output.decode("utf-8").splitlines()
    dispedid = (x.split(",") for x in dispedid)
    dispedid = dict((x,_hash(y.encode("utf-8"))) for x, y in dispedid)
    return dispedid



def script_name(displays):
    edid = get_edid()
    displays = [x[0] + "_" + edid[x[0]] for x in displays]
    return os.path.expanduser(
        os.path.join("~", ".screenlayout", "_".join(displays) + ".sh")
    )


def write_xresource(displays):

    xresourcefile = os.path.expanduser(os.path.join("~", ".Xresources.d", "i3"))
    data = """
! ~/.Xresources.d/i3
! Make sure to include this file from ~/.Xresources by adding
! #include "~/.Xresources.d/i3"
! if there is just a single monitor, all indexes point to the first
! if there are only two monitors, 0 and 1 point to the first and 2 points to the second
"""

    # remove display from list if not connected
    _displays=[]
    for display in displays:
        if display[2]:
            _displays += [display]
    displays = _displays

    numdisplays = len(displays)

    display0 = displays[0]
    if numdisplays == 1:
        display1 = displays[0]
        display2 = displays[0]
    elif numdisplays == 2:
        display1 = displays[0]
        display2 = displays[1]
    elif numdisplays >= 3:
        display1 = displays[1]
        display2 = displays[2]
    else:
        raise(Exception)

    for display in displays:
        if display[1] == "primary":
            primary = display[0]
            break

    data += "\ni3.output.0.name: {}".format(display0[0])
    data += "\ni3.output.0.primary: {}".format(display0[1])
    data += "\ni3.output.0.geometry: {}".format(display0[2])
    data += "\ni3.output.0.orientation: {}".format(display0[3])
    data += "\ni3.output.0.layout: {}".format(display0[4])
    data += "\n"
    data += "\ni3.output.1.name: {}".format(display1[0])
    data += "\ni3.output.1.primary: {}".format(display1[1])
    data += "\ni3.output.1.geometry: {}".format(display1[2])
    data += "\ni3.output.1.orientation: {}".format(display1[3])
    data += "\ni3.output.1.layout: {}".format(display1[4])
    data += "\n"
    data += "\ni3.output.2.name: {}".format(display2[0])
    data += "\ni3.output.2.primary: {}".format(display2[1])
    data += "\ni3.output.2.geometry: {}".format(display2[2])
    data += "\ni3.output.2.orientation: {}".format(display2[3])
    data += "\ni3.output.2.layout: {}".format(display2[4])
    data += "\n"
    data += "\ni3.output.primary: {}".format(primary)
    if numdisplays >= 2:
        data += "\ni3.output.secondary: {}".format(display1[0])
        if numdisplays >= 3:
            data += "\ni3.output.third: {}".format(display2[0])
        data += "\n"

    print(data)

    f = open(xresourcefile, "w")
    f.write(data)
    f.close()

    # Reloading X server resource database utility
    subprocess.run(["xrdb", os.path.expanduser("-I$HOME"),os.path.expanduser("~/.Xresources")], stdout=subprocess.PIPE)
    subprocess.run(["i3-msg", "reload"], stdout=subprocess.PIPE)


def loop(post, once):

    if once:
        new = current_connected_displays()
        handle_x(new, post)
    else:
        previous = ""
        while True:
            new = current_connected_displays()
            if new != previous:
                previous = new
                handle_x(new, post)
            time.sleep(3)


def run_script(path):

    try:
        subprocess.run([path])
    except Exception:
        print(timestamp(), " Not found:   ", path)
        return False
    return True


def handle_x(displays, post):

    arandr_script = script_name(displays)

    print("########################################")
    print("")
    print(timestamp(), " New:        ", displays)
    print(timestamp(), " Executing:  ", arandr_script)
    if run_script(arandr_script):

        displays = current_connected_displays(primary=True)
        print(timestamp(), " Updating i3 Xresources")
        write_xresource(displays)

        if post:
            print(timestamp(), " Executing:    ", post)
            run_script(post)

    print(timestamp(), " Finished.")
    print("")


@click.option("--post", default=None, help="program to run after a change")
@click.option("--once", is_flag=True, help="just run once and update")
@click.command()
def main(post, once):
    if not once:
        instance = tendo.singleton.SingleInstance() #NOQA
    loop(post, once)


if __name__ == "__main__":
    main()
