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
    print (" ".join(message))


def timestamp(ts = None):

    if ts:
        ts = int(ts)
    else:
        ts = time.time()
    return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')


def parse_xrandr_output(text):

    pattern = re.compile(r"^([\w-]+)\sconnected\s(primary)?\s?([0-9+x]+)?\s?.*")
    ret = filter(lambda x: pattern.match(x), text.decode("utf-8").splitlines())
    ret = map(lambda x: pattern.match(x).group(1,2,3), ret)
    displays = sorted(ret, key= lambda x: x[0])
    dimpattern = re.compile(r"([0-9]+)x([0-9]+)[+]([0-9]+)[+]([0-9]+)")
    displayslist=[]
    for display in displays:
        display = list(display)
        dimension = dimpattern.match(display[2])
        w, h, x, y = dimension.group(1,2,3,4)
        ratio = int(w) / int(h)
        if ratio > 2:
            display.append('ultrawide')
            display.append('splith')
        elif ratio > 0:
            display.append('landscape')
            display.append('tabbed')
        else:
            display.append('portrait')
            display.append('splitv')
        displayslist.append(display)
    displays = displayslist
    return displays


def order_displays(displays):

    # order displays from left to right, top to bottom
    # smallest return number comes first
    def _xsort(item):
        if item[2]:
            pattern = re.compile(r"[0-9x]+\+([0-9]+)\+([0-9]+)+")
            x, y = pattern.match(item[2]).group(1,2)
            x, y = int(x), int(y)
            #order = x + 10000 * y
            # order displays from left to right, top to bottom
            order = x
            return order
        else:
            return 0
    ret = sorted(displays, key=_xsort)

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

! output index 0 is the primary monitor, hence i3.output.0 == i3.output.primary
! output index 1 is the first secondary monitor, hence i3.output.1 == i3.output.secondary
! output index 2 is the second secondary monitor, i3.output.2 is the third monitor

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
    print(numdisplays, displays)
    if numdisplays >= 1:
        data += "\ni3.output.0.name: {}".format(displays[0][0])
        data += "\ni3.output.0.primary: {}".format(displays[0][1])
        data += "\ni3.output.0.geometry: {}".format(displays[0][2])
        data += "\ni3.output.0.orientation: {}".format(displays[0][3])
        data += "\ni3.output.0.layout: {}".format(displays[0][4])
        if numdisplays >= 2:
            data += "\n"
            data += "\ni3.output.1.name: {}".format(displays[1][0])
            data += "\ni3.output.1.primary: {}".format(displays[1][1])
            data += "\ni3.output.1.geometry: {}".format(displays[1][2])
            data += "\ni3.output.1.orientation: {}".format(displays[1][3])
            data += "\ni3.output.1.layout: {}".format(displays[1][4])
        elif numdisplays >= 3:
            data += "\n"
            data += "\ni3.output.2.name: {}".format(displays[2][0])
            data += "\ni3.output.2.primary: {}".format(displays[2][1])
            data += "\ni3.output.2.geometry: {}".format(displays[2][2])
            data += "\ni3.output.2.orientation: {}".format(displays[2][3])
            data += "\ni3.output.2.layout: {}".format(displays[2][4])
    else:
        raise(Exception)
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
        print(timestamp(), "Could not run script:", path)
        return False
    return True


def handle_x(displays, post):

    arandr_script = script_name(displays)

    print(timestamp(), " new:", displays, ", calling", arandr_script)
    if run_script(arandr_script):

        displays = current_connected_displays(primary=True)
        print(timestamp(), " now:", displays, ", updating i3 Xresources")
        write_xresource(displays)

        if post:
            print(timestamp(), " running post: ", post)
            run_script(post)

    print(timestamp(), "finished")


@click.option("--post", default=None, help="program to run after a change")
@click.option("--once", is_flag=True, help="just run once and update")
@click.command()
def main(post, once):
    if not once:
        instance = tendo.singleton.SingleInstance() #NOQA
    loop(post, once)


if __name__ == "__main__":
    main()
